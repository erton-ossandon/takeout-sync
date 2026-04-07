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
             Handles missing extensions, platform detection (30+ brands), 
             Nokia legacy logic, and filename truncation.
"""

# --- CONFIGURATION ---
base_directory = '.'
VIDEO_EXTS = ('.mp4', '.m4v', '.mov', '.3gp', '.avi', '.qt')
PHOTO_EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.tif', '.tiff', '.webp', '.gif')

# --- FULL PLATFORM LIBRARY (CHILE & GLOBAL 2010-2024) ---
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

def fix_missing_extensions(folder_path):
    """Phase 0: Identify and fix files without extensions using ExifTool."""
    files = os.listdir(folder_path)
    for f in files:
        full_path = os.path.join(folder_path, f)
        # Only process files that are NOT directories and have NO extension
        if os.path.isfile(full_path) and '.' not in f:
            try:
                print(f"🔍 Identifying extensionless file: {f}")
                cmd = ['exiftool', '-s3', '-FileTypeExtension', full_path]
                ext = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
                if ext:
                    new_name = f"{f}.{ext.lower()}"
                    new_path = os.path.join(folder_path, new_name)
                    os.rename(full_path, new_path)
                    print(f"📝 Renamed: {f} -> {new_name}")
            except: pass

def smart_json_search(media_path, base_name, orig_ext, file_list):
    """Handles Google Takeout truncation (47-51 chars) and moved indices."""
    dir_name = os.path.dirname(media_path)
    attempts = [f"{base_name}{orig_ext}.json", f"{base_name}.json"]
    idx_match = re.search(r'(.*)\((\d+)\)$', base_name)
    if idx_match:
        name_no_idx, idx = idx_match.groups()
        attempts.append(f"{name_no_idx}{orig_ext}({idx}).json")
        attempts.append(f"{name_no_idx}({idx}){orig_ext}.json")
    for name in attempts:
        path = os.path.join(dir_name, name)
        if os.path.exists(path): return path
    if len(base_name) >= 40:
        low_name = base_name.lower()
        for f in file_list:
            if f.lower().endswith('.json') and (f.lower().startswith(low_name[:47]) or f.lower().startswith(low_name[:40])):
                return os.path.join(dir_name, f)
    return None

def detect_final_suffix(make, model, dt_obj, d_json):
    """Comprehensive OS detection including Nokia special logic and nested JSON deviceType."""
    full_info = f"{make or ''} {model or ''}".lower()
    
    # 1. Nokia Specific Eras
    if 'nokia' in full_info:
        if 'lumia' in full_info: return "_WinPhone"
        is_android_mod = re.search(r'nokia [1-9](\.[1-9])?|nokia [gcx][0-9]', full_info)
        if is_android_mod or (dt_obj and dt_obj.year >= 2017): return "_Android"
        return "_Symbian"

    # 2. General Manufacturer Mapping
    for key, suffix in PLATFORM_MAPPING.items():
        if key in full_info: return f"_{suffix}"
        
    # 3. Google Photos JSON deviceType (Nested Path)
    try:
        dtype = d_json['googlePhotosOrigin']['mobileUpload']['deviceType'].upper()
        if dtype == 'IOS_PHONE': return "_iOS"
        if dtype == 'ANDROID_PHONE': return "_Android"
    except (KeyError, TypeError): pass
    return ""

def get_exif_info(media_path):
    try:
        cmd = ['exiftool', '-s3', '-d', '%Y:%m:%d %H:%M:%S', '-DateTimeOriginal', '-SubSecTimeOriginal', '-Make', '-Model', media_path]
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().splitlines()
        dt_str = res.strip() if len(res) > 0 else None
        ms_str = res.strip() if len(res) > 1 else "000"
        make = res.strip() if len(res) > 2 else ""
        model = res.strip() if len(res) > 3 else ""
        dt_obj = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc) if dt_str else None
        return dt_obj, ms_str[:3].ljust(3, '0'), make, model
    except: return None, "000", "", ""

def detect_existing_video_tags(path):
    tags = ['TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate']
    try:
        cmd = ['exiftool', '-s', '-m'] + [f'-{t}' for t in tags] + [path]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
        return [t for t in tags if t.lower() in output]
    except: return []

def process_master(folder_path):
    abs_folder = os.path.abspath(folder_path)
    
    # PHASE 0: Identify and fix extensionless files
    fix_missing_extensions(abs_folder)
    
    print(f"🔍 Scanning folder: {abs_folder}")
    file_list = sorted(os.listdir(abs_folder))
    valid_files = [f for f in file_list if f.lower().endswith(PHOTO_EXTS + VIDEO_EXTS)]
    print(f"Found {len(valid_files)} media files.")

    collection = {}
    for file_name in valid_files:
        base_name, ext = os.path.splitext(file_name)
        media_path = os.path.join(abs_folder, file_name)
        dt_exif, ms_exif, make, model = get_exif_info(media_path)
        json_path = smart_json_search(media_path, base_name, ext, file_list)
        
        d_json, jsons_to_delete = None, []
        if json_path:
            jsons_to_delete.append(json_path)
            try:
                with open(json_path, 'r', encoding='utf-8') as f: d_json = json.load(f)
            except: pass

        ts, dt_obj = None, None
        if dt_exif:
            ts = int(dt_exif.timestamp())
            dt_obj = dt_exif
        elif d_json:
            ts = int(d_json['photoTakenTime']['timestamp'])
            dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            ts = int(os.path.getmtime(media_path))
            dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)

        suffix = detect_final_suffix(make, model, dt_obj, d_json)
        collection[file_name.lower()] = {
            'orig_name': file_name, 'ts': ts, 'ms': ms_exif, 'json': d_json,
            'json_orig': json_path, 'jsons_to_delete': jsons_to_delete, 
            'suffix': suffix, 'base_lower': base_name.lower(),
            'is_video': ext.lower() in VIDEO_EXTS
        }

    # STEP 2: SYNC (Video inherits from Photo)
    photo_dict = {v['base_lower']: k for k, v in collection.items() if not v['is_video']}
    for k, data in collection.items():
        if data['is_video']:
            photo_key = photo_dict.get(data['base_lower'])
            if photo_key:
                ref_p = collection[photo_key]
                data['ts'], data['ms'], data['suffix'] = ref_p['ts'], ref_p['ms'], ref_p['suffix']
                if not data['json']: data['json'] = ref_p['json']

    # STEP 3: PROCESSING
    occupied_times, burst_offsets = {}, {}
    for k in sorted(collection.keys()):
        data = collection[k]
        media_path = os.path.join(abs_folder, data['orig_name'])
        dt_base = datetime.fromtimestamp(data['ts'], tz=timezone.utc)
        
        time_key = dt_base.strftime("%Y%m%d_%H%M%S") + data['ms']
        if time_key in occupied_times:
            if occupied_times[time_key] == data['base_lower']: ms_offset = 0
            else:
                burst_offsets[time_key] = burst_offsets.get(time_key, 0) + 10
                ms_offset = burst_offsets[time_key]
        else:
            occupied_times[time_key], ms_offset = data['base_lower'], 0

        final_dt = dt_base + timedelta(milliseconds=ms_offset)
        ms_final = (data['ms'] if ms_offset == 0 else str(final_dt.microsecond // 1000).zfill(3))
        exif_fmt = final_dt.strftime("%Y:%m:%d %H:%M:%S")

        # EXIFTOOL Writing
        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-n', '-api', 'LargeFileSupport=1', '-api', 'ignoreMinorErrors=1']
        if data['json'] and data['json'].get('geoData', {}).get('latitude', 0.0) != 0.0:
            geo = data['json']['geoData']
            cmd += [f'-GPSLatitude={geo["latitude"]}', f'-GPSLongitude={geo["longitude"]}', f'-GPSAltitude={geo.get("altitude", 0.0)}']
        
        if data['is_video']:
            v_tags = detect_existing_video_tags(media_path)
            cmd += [f'-FileCreateDate={exif_fmt}', f'-FileModifyDate={exif_fmt}', f'-CreateDate={exif_fmt}', f'-ModifyDate={exif_fmt}',
                    f'-CreationDate={exif_fmt}.{ms_final}', '-UserData:DateTimeOriginal=', '-XMP:all=']
            for t in v_tags: cmd.append(f'-{t}={exif_fmt}')
        else:
            cmd += [f'-FileCreateDate={exif_fmt}', f'-FileModifyDate={exif_fmt}', f'-CreateDate={exif_fmt}', f'-ModifyDate={exif_fmt}',
                    f'-DateTimeOriginal={exif_fmt}', f'-SubSecTimeOriginal={ms_final}']
        subprocess.run(cmd + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Move and Rename
        orig_ext = os.path.splitext(data['orig_name'])[1].lower()
        ext_mapping = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}
        final_ext = ext_mapping.get(orig_ext, orig_ext)
        dest_dir = os.path.join(abs_folder, final_dt.strftime("%Y"), final_dt.strftime("%m"))
        os.makedirs(dest_dir, exist_ok=True)
        
        final_base = final_dt.strftime("%Y%m%d_%H%M%S") + ms_final + data['suffix']
        dest_path = os.path.join(dest_dir, final_base + final_ext)

        c = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{final_base}_{c}{final_ext}")
            c += 1
        
        shutil.move(media_path, dest_path)

        if data['json']:
            j_copy = data['json'].copy()
            j_copy['title'] = os.path.basename(dest_path)
            j_copy['photoTakenTime'] = {'timestamp': str(int(final_dt.timestamp())), 'formatted': final_dt.strftime("%d %b %Y %H:%M:%S") + f".{ms_final} UTC"}
            with open(dest_path + ".json", 'w', encoding='utf-8') as fj:
                json.dump(j_copy, fj, indent=2)
            for j_del in data['jsons_to_delete']:
                if os.path.exists(j_del): os.remove(j_del)

        print(f"✅ {data['orig_name']} -> {os.path.relpath(dest_path, abs_folder)}")

    print("\n" + "="*40 + f"\n🚀 PROCESS COMPLETED\n" + "="*40)

if __name__ == "__main__":
    process_master(base_directory)
