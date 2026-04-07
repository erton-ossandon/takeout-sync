import os
import json
import subprocess
import re
import shutil
from datetime import datetime, timezone, timedelta

"""
Script: takeout-sync.py
Description: An advanced automation tool designed to reorganize, rename, and repair 
             metadata for photo and video libraries exported from Google Takeout. 
             It ensures a consistent naming convention while preserving or 
             restoring technical details.
"""

# --- CONFIGURATION ---
base_directory = '.'
VIDEO_EXTS = ('.mp4', '.m4v', '.mov', '.3gp')
PHOTO_EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.tif', '.tiff', '.webp', '.gif')

# --- PLATFORM LIBRARY (MAPPING) ---
PLATFORM_MAPPING = {
    'apple': 'iOS',
    'samsung': 'Android', 'motorola': 'Android', 'xiaomi': 'Android', 'redmi': 'Android',
    'poco': 'Android', 'huawei': 'Android', 'honor': 'Android', 'oppo': 'Android',
    'vivo': 'Android', 'realme': 'Android', 'google': 'Android', 'pixel': 'Android',
    'sony': 'Android', 'htc': 'Android', 'lg': 'Android', 'tcl': 'Android',
    'alcatel': 'Android', 'zte': 'Android', 'oneplus': 'Android', 'asus': 'Android',
    'lenovo': 'Android', 'tecno': 'Android', 'infinix': 'Android', 'itel': 'Android',
    'bgh': 'Android', 'own': 'Android',
    'microsoft': 'WinPhone', 'lumia': 'WinPhone',
    'blackberry': 'BlackBerry', 'rim': 'BlackBerry'
}

def smart_json_search(media_path, base_name, orig_ext, file_list):
    """Resolves Google Takeout truncation (47-51 chars) and moved indices."""
    dir_name = os.path.dirname(media_path)
    
    # 1. Direct and Exact Attempts
    attempts = [f"{base_name}{orig_ext}.json", f"{base_name}.json"]
    
    # 2. Index Handling (Ex: photo(1).jpg -> photo.jpg(1).json)
    idx_match = re.search(r'(.*)\((\d+)\)$', base_name)
    if idx_match:
        name_no_idx, idx = idx_match.groups()
        attempts.append(f"{name_no_idx}{orig_ext}({idx}).json")
        attempts.append(f"{name_no_idx}({idx}){orig_ext}.json")

    for name in attempts:
        path = os.path.join(dir_name, name)
        if os.path.exists(path): return path

    # 3. Dynamic Truncation Window (47 to 40 characters)
    if len(base_name) >= 40:
        low_name = base_name.lower()
        for f in file_list:
            f_low = f.lower()
            if f_low.endswith('.json'):
                # Attempt with 47-char standard cut
                if len(base_name) >= 47 and f_low.startswith(low_name[:47]): return os.path.join(dir_name, f)
                # Attempt with 40-char safety cut
                if f_low.startswith(low_name[:40]): return os.path.join(dir_name, f)
            
    return None

def extract_ms_from_text(text):
    if not text: return None
    match = re.search(r'[.,](\d{1,3})', text)
    return match.group(1).ljust(3, '0')[:3] if match else None

def detect_final_suffix(make, model, dt_date, d_json):
    full_info = f"{make or ''} {model or ''}".lower()
    
    # Nokia Logic (Symbian, WinPhone, Android)
    if 'nokia' in full_info:
        if 'lumia' in full_info: return "_WinPhone"
        is_and_mod = re.search(r'nokia [1-9](\.[1-9])?|nokia [gcx][0-9]', full_info)
        if is_and_mod or (dt_date and dt_date.year >= 2017): return "_Android"
        return "_Symbian"
        
    # General Manufacturers (EXIF)
    for key, suffix in PLATFORM_MAPPING.items():
        if key in full_info: return f"_{suffix}"
        
    # Fallback to JSON deviceType
    if d_json and 'deviceType' in d_json:
        dtype = d_json['deviceType'].upper()
        if dtype == 'IOS_PHONE': return "_iOS"
        if dtype == 'ANDROID_PHONE': return "_Android"
    return ""

def get_exif_info(media_path):
    try:
        cmd = ['exiftool', '-s3', '-d', '%Y:%m:%d %H:%M:%S', 
               '-DateTimeOriginal', '-SubSecTimeOriginal', '-Make', '-Model', media_path]
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().splitlines()
        dt_str = res[0].strip() if len(res) > 0 else None
        ms_str = res[1].strip() if len(res) > 1 else "000"
        make = res[2].strip() if len(res) > 2 else ""
        model = res[3].strip() if len(res) > 3 else ""
        dt_obj = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc) if dt_str else None
        return dt_obj, ms_str[:3].ljust(3, '0'), make, model
    except: return None, "000", "", ""

def detect_existing_tags(path):
    tags = ['TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate']
    try:
        cmd = ['exiftool', '-s', '-m'] + [f'-{t}' for t in tags] + [path]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
        return [t for t in tags if t.lower() in output]
    except: return []

def process_master(folder_path):
    file_list = sorted(os.listdir(folder_path))
    collection = {}
    photos_ok, videos_ok = 0, 0

    # --- STEP 1: DATA COLLECTION ---
    for file_name in file_list:
        base_name, raw_ext = os.path.splitext(file_name)
        ext = raw_ext.lower()
        if ext not in PHOTO_EXTS and ext not in VIDEO_EXTS: continue
        
        media_path = os.path.join(folder_path, file_name)
        dt_exif, ms_exif, make, model = get_exif_info(media_path)
        json_path = smart_json_search(media_path, base_name, ext, file_list)
        
        d_json, jsons_to_delete = None, []
        if json_path:
            jsons_to_delete.append(json_path)
            try:
                with open(json_path, 'r', encoding='utf-8') as f: d_json = json.load(f)
            except: pass

        suffix = detect_final_suffix(make, model, dt_exif, d_json)
        ts, ms = None, "000"
        if dt_exif:
            ts, ms = str(int(dt_exif.timestamp())), ms_exif
        elif d_json:
            ts = d_json['photoTakenTime']['timestamp']
            ms = extract_ms_from_text(d_json['photoTakenTime'].get('formatted', '')) or "000"

        collection[file_name.lower()] = {
            'orig_name': file_name, 'ts': ts, 'ms': ms, 'json': d_json,
            'jsons_to_delete': jsons_to_delete, 'is_video': ext in VIDEO_EXTS, 
            'base_name': base_name.lower(), 'suffix': suffix
        }

    # --- STEP 2: SYNCHRONIZATION (Photos & Videos) ---
    photo_dict = {v['base_name']: k for k, v in collection.items() if not v['is_video'] and v['ts']}
    for k, data in collection.items():
        if data['is_video']:
            photo_key = photo_dict.get(data['base_name'])
            if photo_key:
                ref_photo = collection[photo_key]
                data['ts'], data['ms'], data['suffix'] = ref_photo['ts'], ref_photo['ms'], ref_photo['suffix']
                if not data['json']: data['json'] = ref_photo['json']

    # --- STEP 3: PROCESSING ---
    occupied_times, burst_offsets = {}, {}

    for k in sorted(collection.keys()):
        data = collection[k]
        if not data['ts']: continue
        file_name, base_name, ext = data['orig_name'], *os.path.splitext(data['orig_name'])
        media_path = os.path.join(folder_path, file_name)
        dt_base = datetime.fromtimestamp(int(data['ts']), tz=timezone.utc)
        ms_base = data['ms']

        time_key = dt_base.strftime("%Y%m%d_%H%M%S") + ms_base
        if time_key in occupied_times:
            if occupied_times[time_key] == base_name.lower(): ms_offset = 0
            else:
                burst_offsets[time_key] = burst_offsets.get(time_key, 0) + 10
                ms_offset = burst_offsets[time_key]
        else:
            occupied_times[time_key], ms_offset = base_name.lower(), 0

        dt_final = dt_base + timedelta(milliseconds=ms_offset)
        exif_fmt, ms_fmt = dt_final.strftime("%Y:%m:%d %H:%M:%S"), (ms_base if ms_offset == 0 else str(dt_final.microsecond // 1000).zfill(3))

        # EXIFTOOL (Metadata Write)
        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-n', '-api', 'LargeFileSupport=1', '-api', 'ignoreMinorErrors=1']
        if data['json'] and data['json'].get('geoData', {}).get('latitude', 0.0) != 0.0:
            geo = data['json']['geoData']
            cmd += [f'-GPSLatitude={geo["latitude"]}', f'-GPSLongitude={geo["longitude"]}', f'-GPSAltitude={geo.get("altitude", 0.0)}']
        
        if data['is_video']:
            v_tags = detect_existing_tags(media_path)
            cmd += [f'-FileCreateDate={exif_fmt}', f'-FileModifyDate={exif_fmt}', f'-CreateDate={exif_fmt}', f'-ModifyDate={exif_fmt}',
                    f'-CreationDate={exif_fmt}.{ms_fmt}', '-UserData:DateTimeOriginal=', '-XMP:all=']
            for t in v_tags: cmd.append(f'-{t}={exif_fmt}')
        else:
            cmd += [f'-FileCreateDate={exif_fmt}', f'-FileModifyDate={exif_fmt}', f'-CreateDate={exif_fmt}', f'-ModifyDate={exif_fmt}',
                    f'-DateTimeOriginal={exif_fmt}', f'-SubSecTimeOriginal={ms_fmt}']
        subprocess.run(cmd + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Extension Normalization
        ext_mapping = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}
        final_ext = ext_mapping.get(ext.lower(), ext.lower())
        year_str, month_str = dt_final.strftime("%Y"), dt_final.strftime("%m")
        dest_folder = os.path.join(folder_path, year_str, month_str)
        os.makedirs(dest_folder, exist_ok=True)
        
        final_base_name = dt_final.strftime("%Y%m%d_%H%M%S") + ms_fmt + data['suffix']
        dest_path = os.path.join(dest_folder, final_base_name + final_ext)

        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_folder, f"{final_base_name}_{counter}{final_ext}")
            counter += 1
        shutil.move(media_path, dest_path)

        if data['json']:
            j_copy = data['json'].copy()
            j_copy['title'] = os.path.basename(dest_path)
            j_copy['photoTakenTime'] = {'timestamp': str(int(dt_final.timestamp())), 'formatted': dt_final.strftime("%d %b %Y %H:%M:%S") + f".{ms_fmt} UTC"}
            with open(dest_path + ".json", 'w', encoding='utf-8') as f: json.dump(j_copy, f, indent=2)

        for j_del in data['jsons_to_delete']:
            if os.path.exists(j_del): os.remove(j_del)

        if data['is_video']: videos_ok += 1
        else: photos_ok += 1
        print(f"✅ {file_name} -> {year_str}/{month_str}/{os.path.basename(dest_path)}")

    print("\n" + "="*40 + f"\n🚀 PROCESS COMPLETED\n📸 {photos_ok} Photos | 🎥 {videos_ok} Videos\n" + "="*40)

if __name__ == "__main__":
    process_master(base_directory)
