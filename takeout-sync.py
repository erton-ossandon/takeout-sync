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
        cmd = ['exiftool', '-s3', '-d', '%Y:%m:%d %H:%M:%S', '-DateTimeOriginal', '-SubSecTimeOriginal', '-Make', '-Model', media_path]
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().splitlines()
        dt_str = res[0].strip() if len(res) > 0 and ":" in res[0] else None
        ms_str = res[1].strip() if len(res) > 1 and res[1].strip().isdigit() else "000"
        make = res[2].strip() if len(res) > 2 else ""
        model = res[3].strip() if len(res) > 3 else ""
        dt_obj = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc) if dt_str else None
        return dt_obj, ms_str[:3].zfill(3), make, model
    except: return None, "000", "", ""

def detect_existing_video_tags(path):
    tags = ['TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate']
    try:
        cmd = ['exiftool', '-s', '-m'] + [f'-{t}' for t in tags] + [path]
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
        
        # New Routine: Detect real extension mismatch
        try:
            real_ext_cmd = ['exiftool', '-s3', '-FileTypeExtension', current_path]
            real_ext = subprocess.check_output(real_ext_cmd).decode().strip().lower()
            if real_ext:
                real_ext = f".{real_ext}"
                name_part, old_ext = os.path.splitext(file_name)
                if real_ext != old_ext.lower() and not (real_ext == '.jpg' and old_ext.lower() == '.jpeg'):
                    new_file_name = f"{name_part}{real_ext}"
                    new_path = os.path.join(abs_folder, new_file_name)
                    os.rename(current_path, new_path)
                    file_name = new_file_name
                    current_path = new_path
        except: pass

        base_name, ext = os.path.splitext(file_name)
        media_path = current_path
        dt_exif, ms_exif, make, model = get_exif_info(media_path)
        json_path = smart_json_search(media_path, base_name, ext, file_list)

        d_json = None
        if json_path:
            try:
                with open(json_path, 'r', encoding='utf-8') as f: d_json = json.load(f)
            except: pass

        if dt_exif:
            ts = int(dt_exif.timestamp()); dt_obj = dt_exif
        elif d_json:
            ts = int(d_json['photoTakenTime']['timestamp'])
            dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            ts = int(os.path.getmtime(media_path)); dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)

        is_video = ext.lower() in VIDEO_EXTS
        collection[file_name.lower()] = {
            'orig_name': file_name, 'ts': ts, 'ms': ms_exif, 'json': d_json,
            'json_orig_path': json_path, 'suffix': detect_final_suffix(make, model, dt_obj, d_json),
            'base_lower': base_name.lower(), 'is_video': is_video
        }
        if is_video: video_count += 1
        else: photo_count += 1

    photo_dict = {v['base_lower']: k for k, v in collection.items() if not v['is_video']}
    for k, data in collection.items():
        if data['is_video'] and data['base_lower'] in photo_dict:
            ref = collection[photo_dict[data['base_lower']]]
            data['ts'], data['ms'], data['suffix'] = ref['ts'], ref['ms'], ref['suffix']
            if not data['json']: data['json'] = ref['json']

    sorted_keys = sorted(collection.keys(), key=lambda k: (collection[k]['ts'], re.sub(r'\(\d+\)', '', collection[k]['base_lower']), 1 if '(' in collection[k]['orig_name'] else 0, 1 if collection[k]['is_video'] else 0))
    occupied_times = {}

    for k in sorted_keys:
        data = collection[k]
        media_path = os.path.join(abs_folder, data['orig_name'])
        dt_base = datetime.fromtimestamp(data['ts'], tz=timezone.utc)
        file_identity = data['base_lower']

        try:
            ms_val = int(data['ms'])
        except (ValueError, TypeError):
            ms_val = 0

        while True:
            time_key = dt_base.strftime("%Y%m%d_%H%M%S") + str(ms_val).zfill(3)
            if time_key in occupied_times and occupied_times[time_key] != file_identity:
                ms_val = (ms_val + 10)
                continue
            occupied_times[time_key] = file_identity
            break

        final_dt = dt_base.replace(microsecond=0) + timedelta(milliseconds=ms_val)
        ms_final = str(ms_val).zfill(3)
        exif_fmt = final_dt.strftime("%Y:%m:%d %H:%M:%S")
        exif_fmt_utc = f"{exif_fmt}+00:00"

        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-api', 'LargeFileSupport=1']
        CLEANUP_TAGS = ['-XMP-X:XMPToolkit=', '-*URL=', '-CreatorTool=']

        if data['json'] and data['json'].get('geoData', {}).get('latitude', 0.0) != 0.0:
            geo = data['json']['geoData']
            cmd += [f'-GPSLatitude={geo["latitude"]}', f'-GPSLongitude={geo["longitude"]}', f'-GPSAltitude={geo.get("altitude", 0.0)}']

        if data['is_video']:
            v_tags = detect_existing_video_tags(media_path)
            cmd += [f'-FileCreateDate#={exif_fmt_utc}', f'-FileModifyDate#={exif_fmt_utc}',
                    f'-CreateDate#={exif_fmt}', f'-ModifyDate#={exif_fmt}',
                    f'-Keys:CreationDate#={exif_fmt}.{ms_final}', '-UserData:DateTimeOriginal=']
            cmd += CLEANUP_TAGS
            for t in v_tags: cmd.append(f'-{t}#={exif_fmt}')
        else:
            cmd += [f'-FileCreateDate#={exif_fmt_utc}', f'-FileModifyDate#={exif_fmt_utc}',
                    f'-CreateDate={exif_fmt}', f'-ModifyDate={exif_fmt}',
                    f'-DateTimeOriginal={exif_fmt}', f'-SubSecTimeOriginal={ms_final}']
            cmd += CLEANUP_TAGS
        
        subprocess.run(cmd + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        _, ext_orig_raw = os.path.splitext(data['orig_name'])
        ext_orig = ext_orig_raw.lower()
        
        ext = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}.get(ext_orig, ext_orig)
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
                "geoData": orig.get("geoData", {
                    "latitude": 0.0, "longitude": 0.0, "altitude": 0.0,
                    "latitudeSpan": 0.0, "longitudeSpan": 0.0
                }),
                "geoDataExif": orig.get("geoDataExif", {
                    "latitude": 0.0, "longitude": 0.0, "altitude": 0.0,
                    "latitudeSpan": 0.0, "longitudeSpan": 0.0
                }),
                "url": "",
                "googlePhotosOrigin": orig.get("googlePhotosOrigin", {
                    "mobileUpload": {"deviceType": "UNKNOWN"}
                })
            }
            
            with open(dest_path + ".json", 'w', encoding='utf-8') as fj:
                json.dump(new_json, fj, indent=2, ensure_ascii=False)

            if data['json_orig_path'] and os.path.exists(data['json_orig_path']):
                os.remove(data['json_orig_path'])

        print(f"✅ {data['orig_name']} -> {os.path.relpath(dest_path, abs_folder)} (ms: {ms_final})")

    print("\n" + "="*40 + f"\n🚀 PROCESS COMPLETED\n📸 Photos: {photo_count}\n🎥 Videos: {video_count}\n" + "="*40)

if __name__ == "__main__":
    process_master(base_directory)
