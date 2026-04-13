import os
import json
import subprocess
import re
import shutil
from datetime import datetime, timezone, timedelta

base_directory = '.'
VIDEO_EXTS = ('.mp4', '.m4v', '.mov', '.3gp', '.avi', '.qt')
PHOTO_EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.tif', '.tiff', '.webp', '.gif')

PLATFORM_MAPPING = {
    'apple': 'iOS', 'samsung': 'Android', 'motorola': 'Android', 'xiaomi': 'Android',
    'redmi': 'Android', 'poco': 'Android', 'huawei': 'Android', 'honor': 'Android',
    'oppo': 'Android', 'vivo': 'Android', 'realme': 'Android', 'google': 'Android',
    'pixel': 'Android', 'sony': 'Android', 'htc': 'Android', 'lg': 'Android',
    'tcl': 'Android', 'alcatel': 'Android', 'zte': 'Android', 'oneplus': 'Android',
    'asus': 'Android', 'lenovo': 'Android', 'tecno': 'Android', 'infinix': 'Android',
    'itel': 'Android', 'bgh': 'Android', 'own': 'Android', 'microsoft': 'WinPhone',
    'lumia': 'WinPhone', 'blackberry': 'BlackBerry', 'rim': 'BlackBerry'
}

def fix_missing_extensions(folder_path):
    files = os.listdir(folder_path)
    for f in files:
        full_path = os.path.join(folder_path, f)
        if os.path.isfile(full_path) and '.' not in f:
            try:
                cmd = ['exiftool', '-s3', '-FileTypeExtension', full_path]
                ext = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
                if ext:
                    new_name = f"{f}.{ext.lower()}"
                    os.rename(full_path, os.path.join(folder_path, new_name))
            except: pass

def smart_json_search(media_path, base_name, orig_ext, file_list):
    dir_name = os.path.dirname(media_path)
    attempts = [f"{base_name}{orig_ext}.json", f"{base_name}.json"]
    idx_match = re.search(r'(.*)\((\d+)\)$', base_name)
    if idx_match:
        name_no_idx, idx = idx_match.groups()
        attempts.extend([f"{name_no_idx}{orig_ext}({idx}).json", f"{name_no_idx}({idx}){orig_ext}.json"])
    if len(base_name) > 5:
        attempts.append(f"{base_name[:-1]}.json")
    for name in attempts:
        path = os.path.join(dir_name, name)
        if os.path.exists(path): return path
    return None

def get_exif_info(media_path):
    try:
        cmd = ['exiftool', '-s3', '-d', '%Y:%m:%d %H:%M:%S', '-DateTimeOriginal', '-CreateDate', '-SubSecTimeOriginal', '-Make', '-Model', '-OffsetTime', media_path]
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().splitlines()
        dt_str = res[0].strip() if len(res) > 0 and ":" in res[0] else (res[1].strip() if len(res) > 1 and ":" in res[1] else None)
        ms_str = res[2].strip() if len(res) > 2 and res[2].strip().isdigit() else ""
        make = res[3].strip() if len(res) > 3 else ""
        model = res[4].strip() if len(res) > 4 else ""
        offset = res[5].strip() if len(res) > 5 else ""
        dt_obj = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc) if dt_str else None
        return dt_obj, ms_str[:3].zfill(3) if ms_str else "", make, model, offset
    except: return None, "", "", "", ""

def detect_existing_video_tags(path):
    tags = ['TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate', 'OffsetTime', 'OffsetTimeOriginal', 'OffsetTimeDigitized', 'SubSecTime', 'SubSecTimeOriginal', 'SubSecTimeDigitized']
    try:
        cmd = ['exiftool', '-s', '-m', path]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
        return [t for t in tags if t.lower() in output]
    except: return []

def detect_existing_image_tags(path):
    tags = ['OffsetTime', 'OffsetTimeOriginal', 'OffsetTimeDigitized', 'SubSecTime', 'SubSecTimeOriginal', 'SubSecTimeDigitized']
    try:
        cmd = ['exiftool', '-s', '-m', path]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
        return [t for t in tags if t.lower() in output]
    except: return []

def detect_final_suffix(make, model, dt_obj, d_json):
    full_info = f"{make or ''} {model or ''}".lower()
    if 'nokia' in full_info:
        if 'lumia' in full_info: return "_WinPhone"
        if re.search(r'nokia [1-9](\.[1-9])?|nokia [gcx][0-9]', full_info) or (dt_obj and dt_obj.year >= 2017): return "_Android"
        return "_Symbian"
    for key, suffix in PLATFORM_MAPPING.items():
        if key in full_info: return f"_{suffix}"
    try:
        dtype = d_json['googlePhotosOrigin']['mobileUpload']['deviceType'].upper()
        if 'IOS' in dtype: return "_iOS"
        if 'ANDROID' in dtype: return "_Android"
    except: pass
    return ""

def process_master(folder_path):
    abs_folder = os.path.abspath(folder_path)
    fix_missing_extensions(abs_folder)
    file_list = sorted(os.listdir(abs_folder))
    valid_files = [f for f in file_list if f.lower().endswith(PHOTO_EXTS + VIDEO_EXTS)]
    print(f"Found {len(valid_files)} media files.")

    collection = {}
    photo_count = video_count = 0

    for file_name in valid_files:
        current_path = os.path.join(abs_folder, file_name)
        base_name_orig, ext_orig = os.path.splitext(file_name)
        json_path = smart_json_search(current_path, base_name_orig, ext_orig, file_list)

        try:
            real_ext_cmd = ['exiftool', '-s3', '-FileTypeExtension', current_path]
            real_ext = subprocess.check_output(real_ext_cmd).decode().strip().lower()
            if real_ext:
                real_ext = f".{real_ext}"
                if real_ext != ext_orig.lower() and not (real_ext == '.jpg' and ext_orig.lower() == '.jpeg'):
                    new_file_name = f"{base_name_orig}{real_ext}"
                    new_path = os.path.join(abs_folder, new_file_name)
                    os.rename(current_path, new_path)
                    file_name = new_file_name
                    current_path = new_path
        except: pass

        base_name, ext = os.path.splitext(file_name)
        media_path = current_path
        dt_exif, ms_exif, make, model, offset = get_exif_info(media_path)

        d_json = None
        if json_path:
            try:
                with open(json_path, 'r', encoding='utf-8') as f: d_json = json.load(f)
            except: pass

        if dt_exif:
            ts = int(dt_exif.timestamp()); dt_obj = dt_exif
        elif d_json:
            ts = int(d_json['photoTakenTime']['timestamp'])
            ts_sec = ts / 1000.0 if ts > 9999999999 else ts
            dt_obj = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        else:
            ts = int(os.path.getmtime(media_path)); dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)

        is_video = ext.lower() in VIDEO_EXTS
        collection[file_name.lower()] = {
            'orig_name': file_name, 'ts': ts, 'ms': ms_exif, 'json': d_json,
            'json_orig_path': json_path, 'suffix': detect_final_suffix(make, model, dt_obj, d_json),
            'base_lower': base_name.lower(), 'is_video': is_video, 'offset': offset
        }
        if is_video: video_count += 1
        else: photo_count += 1

    photo_dict = {v['base_lower']: k for k, v in collection.items() if not v['is_video']}
    for k, data in collection.items():
        if data['is_video'] and data['base_lower'] in photo_dict:
            ref = collection[photo_dict[data['base_lower']]]
            data['ts'], data['ms'], data['suffix'], data['offset'] = ref['ts'], ref['ms'], ref['suffix'], ref['offset']
            if not data['json']: data['json'] = ref['json']

    sorted_keys = sorted(collection.keys(), key=lambda k: (collection[k]['ts'], re.sub(r'\(\d+\)', '', collection[k]['base_lower']), 1 if '(' in collection[k]['orig_name'] else 0, 1 if collection[k]['is_video'] else 0))
    
    occupied_times = {}
    last_ms_per_second = {}

    for k in sorted_keys:
        data = collection[k]
        media_path = os.path.join(abs_folder, data['orig_name'])
        ts_val = data['ts']
        ts_sec = ts_val / 1000.0 if ts_val > 9999999999 else ts_val
        dt_base = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        file_identity = data['base_lower']
        second_key = dt_base.strftime("%Y%m%d_%H%M%S")

        if data['ms']:
            ms_val = int(data['ms'])
        else:
            if second_key in last_ms_per_second:
                ms_val = last_ms_per_second[second_key] + 10
            else:
                ms_val = 0

        while True:
            time_key = second_key + str(ms_val).zfill(3)
            if time_key in occupied_times and occupied_times[time_key] != file_identity:
                ms_val += 10
                continue
            occupied_times[time_key] = file_identity
            last_ms_per_second[second_key] = ms_val
            break

        final_dt = dt_base.replace(microsecond=0) + timedelta(milliseconds=ms_val)
        ms_final = str(ms_val).zfill(3)
        exif_fmt = final_dt.strftime("%Y:%m:%d %H:%M:%S")
        val = data['offset'] if data['offset'] else ''

        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-api', 'LargeFileSupport=1']
        CLEANUP_TAGS = [
            '-XMP:XMPToolkit=', '-XMP-dc:Description=', '-XMP-xmp:CreatorTool=',
            '-XMP:CreateDate=', '-XMP:ModifyDate=', '-XMP:DateTimeOriginal=',
            '-photoshop:DateCreated=', '-photoshop:History=',
            '-OffsetTime=', '-OffsetTimeOriginal=', '-OffsetTimeDigitized=',
            '-SubSecTime=', '-SubSecTimeOriginal=', '-SubSecTimeDigitized='
        ]
        cmd += CLEANUP_TAGS

        if data['json'] and (data['json'].get('geoData', {}).get('latitude', 0.0) != 0.0 or data['json'].get('geoData', {}).get('longitude', 0.0) != 0.0):
            geo = data['json']['geoData']
            cmd += [f'-GPSLatitude={geo.get("latitude", 0.0)}', f'-GPSLongitude={geo.get("longitude", 0.0)}', f'-GPSAltitude={geo.get("altitude", 0.0)}']

        if data['is_video']:
            v_tags = detect_existing_video_tags(media_path)
            cmd += [f'-FileCreateDate#={exif_fmt}{val}', f'-FileModifyDate#={exif_fmt}{val}',
                    f'-CreateDate#={exif_fmt}', f'-ModifyDate#={exif_fmt}',
                    f'-DateTimeOriginal#={exif_fmt}', '-UserData:DateTimeOriginal=']
            
            keys_val = exif_fmt
            if ms_final != '000': keys_val += f".{ms_final}"
            if val.strip(): keys_val += f"{val}"
            cmd.append(f'-Keys:CreationDate#={keys_val}')

            if 'TrackCreateDate' in v_tags: cmd.append(f'-TrackCreateDate#={exif_fmt}')
            if 'TrackModifyDate' in v_tags: cmd.append(f'-TrackModifyDate#={exif_fmt}')
            if 'MediaCreateDate' in v_tags: cmd.append(f'-MediaCreateDate#={exif_fmt}')
            if 'MediaModifyDate' in v_tags: cmd.append(f'-MediaModifyDate#={exif_fmt}')
            if 'OffsetTime' in v_tags: cmd.append(f'-OffsetTime#={val}')
            if 'OffsetTimeOriginal' in v_tags: cmd.append(f'-OffsetTimeOriginal#={val}')
            if 'OffsetTimeDigitized' in v_tags: cmd.append(f'-OffsetTimeDigitized#={val}')
            if 'SubSecTime' in v_tags: cmd.append(f'-SubSecTime={ms_final}')
            if 'SubSecTimeOriginal' in v_tags: cmd.append(f'-SubSecTimeOriginal={ms_final}')
            if 'SubSecTimeDigitized' in v_tags: cmd.append(f'-SubSecTimeDigitized={ms_final}')
        else:
            i_tags = detect_existing_image_tags(media_path)
            cmd += [f'-FileCreateDate#={exif_fmt}{val}', f'-FileModifyDate#={exif_fmt}{val}',
                    f'-CreateDate#={exif_fmt}', f'-ModifyDate#={exif_fmt}',
                    f'-DateTimeOriginal#={exif_fmt}']
            
            if 'OffsetTime' in i_tags: cmd.append(f'-OffsetTime#={val}')
            if 'OffsetTimeOriginal' in i_tags: cmd.append(f'-OffsetTimeOriginal#={val}')
            if 'OffsetTimeDigitized' in i_tags: cmd.append(f'-OffsetTimeDigitized#={val}')
            if 'SubSecTime' in i_tags: cmd.append(f'-SubSecTime={ms_final}')
            if 'SubSecTimeOriginal' in i_tags: cmd.append(f'-SubSecTimeOriginal={ms_final}')
            if 'SubSecTimeDigitized' in i_tags: cmd.append(f'-SubSecTimeDigitized={ms_final}')
        
        subprocess.run(cmd + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        _, ext_orig_raw = os.path.splitext(data['orig_name'])
        ext = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}.get(ext_orig_raw.lower(), ext_orig_raw.lower())
        dest_dir = os.path.join(abs_folder, final_dt.strftime("%Y"), final_dt.strftime("%m"))
        os.makedirs(dest_dir, exist_ok=True)

        final_base = f"{final_dt.strftime('%Y%m%d_%H%M%S')}{ms_final}{data['suffix']}"
        dest_path = os.path.join(dest_dir, f"{final_base}{ext}")

        c = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{final_base}_{c}{ext}")
            c += 1

        shutil.move(media_path, dest_path)

        if data['json']:
            orig = data['json']
            ts_millis = str(int(final_dt.timestamp() * 1000))
            fmt_str = final_dt.strftime("%d %b %Y %H:%M:%S") + f".{ms_final} UTC"
            time_obj = {'timestamp': ts_millis, 'formatted': fmt_str}

            new_json = {
                "title": os.path.basename(dest_path),
                "description": orig.get("description", ""),
                "imageViews": "",
                "creationTime": time_obj,
                "photoTakenTime": time_obj,
                "geoData": orig.get("geoData", {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0}),
                "geoDataExif": orig.get("geoDataExif", {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0}),
                "url": "",
                "googlePhotosOrigin": orig.get("googlePhotosOrigin", {"mobileUpload": {"deviceType": "UNKNOWN"}})
            }
            with open(dest_path + ".json", 'w', encoding='utf-8') as fj:
                json.dump(new_json, fj, indent=2, ensure_ascii=False)
            if data['json_orig_path'] and os.path.exists(data['json_orig_path']):
                os.remove(data['json_orig_path'])

        print(f"✅ {data['orig_name']} -> {os.path.relpath(dest_path, abs_folder)} (ms: {ms_final})")

    print("\n" + "="*40 + f"\n🚀 PROCESS COMPLETED\n📸 Photos: {photo_count}\n🎥 Videos: {video_count}\n" + "="*40)

if __name__ == "__main__":
    process_master(base_directory)
