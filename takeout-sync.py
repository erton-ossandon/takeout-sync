import os
import json
import subprocess
import re
import shutil
import pytz
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder
from tzlocal import get_localzone
base_directory = '.'
VIDEO_EXTS = ('.mp4', '.m4v', '.mov', '.3gp', '.avi', '.qt')
PHOTO_EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.tif', '.tiff', '.webp', '.gif')
tf = TimezoneFinder()
neighbor_tz = None
PLATFORM_MAPPING = {
    'apple': 'iOS', 'samsung': 'Android', 'motorola': 'Android', 'xiaomi': 'Android',
    'redmi': 'Android', 'poco': 'Android', 'huawei': 'Android', 'honor': 'Android',
    'oppo': 'Android', 'vivo': 'Android', 'realme': 'Android', 'google': 'Android',
    'pixel': 'Android', 'sony': 'Android', 'htc': 'Android', 'lg': 'Android',
    'tcl': 'Android', 'alcatel': 'Android', 'zte': 'Android', 'oneplus': 'Android',
    'asus': 'Android', 'lenovo': 'Android', 'tecno': 'Android', 'infinix': 'Android',
    'itel': 'Android', 'bgh': 'Android', 'own': 'Android', 'microsoft': 'WinPhone',
    'lumia': 'WinPhone', 'blackberry': 'BlackBerry', 'rim': 'BlackBerry',
    'q10': 'BlackBerry', 'z10': 'BlackBerry'
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
def get_media_metadata(media_path):
    try:
        cmd = ['exiftool', '-G1', '-a', '-s', media_path]
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').splitlines()
        
        meta = {}
        for line in res:
            match = re.match(r'\[(.*?)\]\s+(.*?)\s+:\s+(.*)', line)
            if match:
                group, tag, value = match.groups()
                meta[f"{group}:{tag}"] = value.strip()
        def get_m(keys):
            for k in keys:
                if '*' in k:
                    pattern = k.replace('*', '.*')
                    for meta_key in meta.keys():
                        if re.match(pattern, meta_key): return meta[meta_key]
                elif k in meta: return meta[k]
            return ""
        xmp_tool = get_m(['XMP:XMPToolkit', 'XMP-x:XMPToolkit'])
        xmp_dt = get_m(['XMP:CreateDate', 'XMP:DateTimeDigitized', 'XMP-xmp:CreateDate', 'XMP-exif:DateTimeDigitized',
                        'XMP:ModifyDate', 'XMP:DateTime', 'XMP-xmp:ModifyDate', 'XMP-exif:ModifyDate'])
        xmp_dc_dt = get_m(['XMP:DateTimeOriginal', 'XMP-photoshop:DateCreated', 'XMP-exif:DateTimeOriginal'])
        exif_dt = get_m(['EXIF:CreateDate', 'EXIF:DateTimeDigitized', 'ExifIFD:CreateDate', 'IFD0:CreateDate',
                         'EXIF:ModifyDate', 'EXIF:DateTime', 'ExifIFD:ModifyDate', 'IFD0:ModifyDate'])
        exif_dto_dt = get_m(['EXIF:DateTimeOriginal', 'ExifIFD:DateTimeOriginal'])
        exif_ot_dt = get_m(['EXIF:OffsetTimeDigitized', 'ExifIFD:OffsetTimeDigitized', 'EXIF:OffsetTimeOriginal', 'ExifIFD:OffsetTimeOriginal', 'EXIF:OffsetTime', 'ExifIFD:OffsetTime'])
        exif_sst_dt = get_m(['EXIF:SubSecTimeDigitized', 'ExifIFD:SubSecTimeDigitized', 'EXIF:SubSecTimeOriginal', 'ExifIFD:SubSecTimeOriginal', 'EXIF:SubSecTime', 'ExifIFD:SubSecTime'])
        qt_dt = get_m(['QuickTime:CreateDate', 'QuickTime:ModifyDate'])
        qt_track_dt = get_m(['Track*:TrackCreateDate', 'Track*:CreateDate'])
        qt_media_dt = get_m(['Track*:MediaCreateDate', 'Track*:MediaModifyDate'])
        keys_dt = get_m(['Keys:CreationDate'])
        make = get_m(['Keys:Make', 'XMP:Make', 'EXIF:Make', 'IFD0:Make'])
        model = get_m(['Keys:Model', 'XMP:Model', 'EXIF:Model', 'IFD0:Model'])
        return (xmp_tool, xmp_dt, xmp_dc_dt, 
                exif_dt, exif_dto_dt, exif_ot_dt, exif_sst_dt, 
                qt_dt, qt_track_dt, qt_media_dt, keys_dt, make, model)
    except:
        return ("", "", "", "", "", "", "", "", "", "", "", "", "")
def get_cascade_offset(lat, lon, local_dt, neighbor_tz):
    selected_tz_name = None
    if lat and lon and lat != 0.0 and lon != 0.0:
        selected_tz_name = tf.timezone_at(lng=lon, lat=lat)
    if not selected_tz_name and neighbor_tz:
        selected_tz_name = neighbor_tz
    if not selected_tz_name:
        return None, None
    tz = pytz.timezone(selected_tz_name)
    localized_dt = tz.localize(local_dt)
    offset_str = localized_dt.strftime('%z')
    formatted_offset = f"{offset_str[:3]}:{offset_str[3:]}"
    return formatted_offset, selected_tz_name
def update_media_metadata(media_path, json_dt, offset_str, ms_str_json, extracted_data):
    (x_tool, x_dt, x_dc_dt, e_dt, e_dto_dt, e_ot, e_sst, 
     q_dt, q_track_dt, q_media_dt, k_dt, make, model) = extracted_data
    final_offset = e_ot if (e_ot and any(c in e_ot for c in '+-')) else offset_str
    try:
        ms_numeric = int(ms_str_json) if ms_str_json else 0
    except:
        ms_numeric = 0
    has_ms = True if (e_sst or ms_str_json != "") else False
    if has_ms:
        ms_val_raw = e_sst if e_sst else ms_str_json
        ms = ms_val_raw[:3].zfill(3)
    else:
        ms = ""
    local_str = json_dt.strftime("%Y:%m:%d %H:%M:%S")
    try:
        if final_offset.startswith('-'): sign = 1
        elif final_offset.startswith('+'): sign = -1
        else: sign = 0 
        hrs, mins = int(final_offset[1:3]), int(final_offset[4:6])
        dt_utc = json_dt + timedelta(hours=sign*hrs, minutes=sign*mins)
        qt_date = dt_utc.strftime("%Y-%m-%d")
        qt_time = dt_utc.strftime("%H:%M:%S")
        qt_fmt = f"{qt_date}T{qt_time}Z"
    except:
        qt_fmt = local_str.replace(" ", "T") + "Z"
    iso_date = local_str[:10].replace(":", "-")
    iso_time = local_str[11:]
    iso_suffix = f".{ms}" if ms else ""
    iso_fmt = f"{iso_date}T{iso_time}{iso_suffix}{final_offset if final_offset else ''}"
    keys_val = local_str
    if ms:
        keys_val += f".{ms}"
    if final_offset:
        keys_val += final_offset
    final_make = make
    final_model = model
    if make:
        brand_lower = make.lower()
        for key, value in PLATFORM_MAPPING.items():
            if key in brand_lower:
                final_make = value
                break
    clean_off = final_offset.replace(":", "") if final_offset and ":" in final_offset else (final_offset if final_offset else "UTC")
    return local_str, qt_fmt, keys_val, final_offset, ms, final_make, final_model, clean_off, iso_fmt, has_ms
def detect_final_suffix(make, model, dt_obj, d_json):
    full_info = f"{make or ''} {model or ''}".lower().strip()
    if full_info:
        if 'nokia' in full_info:
            if re.search(r'nokia [1-9](\.[1-9])?|nokia [gcx][0-9]', full_info) or (dt_obj and dt_obj.year >= 2017): return "_Android"
            return "_Symbian"
        for key, suffix in PLATFORM_MAPPING.items():
            if key in full_info:
                return f"_{suffix}"
    if d_json:
        try:
            dtype = d_json['googlePhotosOrigin']['mobileUpload']['deviceType'].upper()
            if 'IOS' in dtype: return "_iOS"
            if 'ANDROID' in dtype: return "_Android"
        except: pass
    return ""
def process_master(folder_path):
    global neighbor_tz
    abs_folder = os.path.abspath(folder_path)
    fix_missing_extensions(abs_folder)
    file_list = sorted(os.listdir(abs_folder))
    valid_files = [f for f in file_list if f.lower().endswith(PHOTO_EXTS + VIDEO_EXTS)]
    print(f"Found {len(valid_files)} media files.")
    collection = {}
    known_geos = []
    identified_tzs = set()
    photo_count = video_count = 0
    for file_name in valid_files:
        current_path = os.path.join(abs_folder, file_name)
        base_name_orig, ext_orig = os.path.splitext(file_name)
        base_lower = base_name_orig.lower() 
        json_path = smart_json_search(current_path, base_name_orig, ext_orig, file_list)
        extracted_data = get_media_metadata(current_path)
        (x_tool, x_dt, x_dc_dt, e_dt, e_dto_dt, e_ot, e_sst, 
         q_dt, q_track_dt, q_media_dt, k_dt, make, model) = extracted_data
#        # ==========================================================
#        # 🔎 CAPTURE DEBUG (TAKEOUT-SYNC)
#        # ==========================================================
#        print(f"\n--- [CAPTURE DEBUG: {file_name}] ---")
#        print(f"XMP Tool:    '{x_tool}'")
#        print(f"XMP Date:    '{x_dt}'")
#        print(f"XMP Create:  '{x_dc_dt}'")
#        print(f"EXIF Date:   '{e_dt}'")
#        print(f"EXIF Orig:   '{e_dto_dt}'")
#        print(f"EXIF Offset: '{e_ot}'")
#        print(f"EXIF SubSec: '{e_sst}'")
#        print(f"QT Date:     '{q_dt}'")
#        print(f"QT Track:    '{q_track_dt}'")
#        print(f"QT Media:    '{q_media_dt}'")
#        print(f"Keys Apple:  '{k_dt}'")
#        print("-" * 40)
#        # ==========================================================
        d_json = None
        geo_payload = []
        if json_path:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    d_json = json.load(f)
            except: pass
        archivo_dt_str = e_dt or x_dt or q_dt
        dt_obj, ts = None, None
        if archivo_dt_str:
            try:
                dt_obj = datetime.strptime(archivo_dt_str[:19], "%Y:%m:%d %H:%M:%S")
                if not (e_dt or x_dt) and q_dt and final_offset:
                    match = re.match(r'([+-])(\d{2}):(\d{2})', final_offset)
                    if match:
                        sign, hh, mm = match.groups()
                        delta = timedelta(hours=int(hh), minutes=int(mm))
                        dt_obj = dt_obj + (delta if sign == '-' else -delta)
                ts = int(dt_obj.timestamp())
            except:
                dt_obj, ts = None, None
        else:
            dt_obj, ts = None, None
        if not dt_obj and d_json:
            ts = int(d_json.get('photoTakenTime', {}).get('timestamp', 0))
            dt_obj = datetime.fromtimestamp(ts)
        if not dt_obj:
            ts = int(os.path.getmtime(current_path))
            dt_obj = datetime.fromtimestamp(ts)
        if d_json:
            lat = d_json.get('geoData', {}).get('latitude')
            lon = d_json.get('geoData', {}).get('longitude')
            alt = d_json.get('geoData', {}).get('altitude', 0.0)
            if lat and lon and lat != 0.0:
                geo_payload = [f'-GPSLatitude={lat}', f'-GPSLongitude={lon}', f'-GPSAltitude={alt}']
        else:
            lat, lon = None, None
        final_offset, tz_name = get_cascade_offset(lat, lon, dt_obj, neighbor_tz)
        if tz_name:
            neighbor_tz = tz_name
            known_geos.append((ts, final_offset, tz_name))
            identified_tzs.add(tz_name)
        elif final_offset:
            known_geos.append((ts, final_offset, None))
        is_video = file_name.lower().endswith(VIDEO_EXTS)
        temp_make = make
        if make:
            brand_lower = make.lower()
            for k_map, v_map in PLATFORM_MAPPING.items():
                if k_map in brand_lower:
                    temp_make = v_map
                    break
        current_suffix = detect_final_suffix(temp_make, model, dt_obj, d_json)
        ms_real = str(e_sst).strip() if e_sst else ""
        collection[file_name.lower()] = {
            'orig_name': file_name, 'ts': ts, 'ms': ms_real, 'json': d_json, 
            'json_orig_path': json_path, 'base_lower': base_lower, 
            'is_video': is_video, 'offset': final_offset, 'dt_obj': dt_obj,
            'extracted_data': extracted_data, 'geo_payload': geo_payload, 'suffix': current_suffix
        }
        if is_video: video_count += 1
        else: photo_count += 1
    known_geos.sort()
    threshold_24h = 86400
    tz_list = sorted(list(identified_tzs))
    local_tz_name = get_localzone().key if hasattr(get_localzone(), 'key') else str(get_localzone())
    for k, data in collection.items():
        if not data['offset']:
            closest_data = None
            if known_geos:
                closest_data = min(known_geos, key=lambda x: abs(x[0] - data['ts']))
            if closest_data and abs(closest_data[0] - data['ts']) <= threshold_24h:
                data['offset'] = closest_data[1]
            else:
                print(f"\n⚠️ SIN ZONA: {data['orig_name']} ({data['dt_obj'].strftime('%Y-%m-%d %H:%M:%S')} UTC)")
                suggestions = tz_list if tz_list else [local_tz_name]
                print(f"Sugerencias: " + ", ".join([f"{i+1}. {z}" for i, z in enumerate(suggestions)]))
                choice = input(f"Elija número o escriba zona (Enter para {suggestions[0]}): ").strip()
                selected_tz = None
                if not choice:
                    selected_tz = suggestions[0]
                elif choice.isdigit() and 0 < int(choice) <= len(suggestions):
                    selected_tz = suggestions[int(choice)-1]
                elif choice in pytz.all_timezones:
                    selected_tz = choice
                if selected_tz:
                    tz_calc = pytz.timezone(selected_tz)
                    loc_dt = tz_calc.localize(data['dt_obj'].replace(tzinfo=None))
                    off_str = loc_dt.strftime('%z')
                    new_off = f"{off_str[:3]}:{off_str[3:]}"
                    data['offset'] = new_off
                    identified_tzs.add(selected_tz)
                    tz_list = sorted(list(identified_tzs))
                else:
                    print("Se mantiene en UTC.")
    photo_dict = {v['base_lower']: k for k, v in collection.items() if not v['is_video']}
    for k, data in collection.items():
        if data['is_video'] and data['base_lower'] in photo_dict:
            ref = collection[photo_dict[data['base_lower']]]
            data['ts'] = ref['ts']
            data['ms'] = ref['ms']
            data['dt_obj'] = ref['dt_obj']
            data['offset'] = ref['offset']
            data['suffix'] = ref['suffix']
            if not data['json']: data['json'] = ref['json']
    sorted_keys = sorted(collection.keys(), key=lambda k: (
        collection[k]['ts'], 
        re.sub(r'\(\d+\)', '', collection[k]['base_lower']), 
        1 if collection[k]['is_video'] else 0
    ))
    occupied_times = {}
    last_ms_per_second = {}
    for k in sorted_keys:
        data = collection[k]
        media_path = os.path.join(abs_folder, data['orig_name'])
        ts_val = data['ts']
        ts_sec = ts_val / 1000.0 if ts_val > 9999999999 else ts_val
        dt_base = datetime.fromtimestamp(ts_sec).replace(tzinfo=None)
        file_identity = data['base_lower']
        second_key = dt_base.strftime("%Y%m%d_%H%M%S")
        ms_str_raw = str(data.get('ms', '')).strip()
        if ms_str_raw.isdigit():
            ms_val = int(ms_str_raw)
        else:
            ms_val = last_ms_per_second.get(second_key, 0)
        while True:
            time_key = second_key + str(ms_val).zfill(3)
            if time_key in occupied_times:
                if occupied_times[time_key] == file_identity:
                    break
                else:
                    ms_val += 1
                    if ms_val >= 1000:
                        ms_val = 0
                        dt_base += timedelta(seconds=1)
                        second_key = dt_base.strftime("%Y%m%d_%H%M%S")
                    continue
            occupied_times[time_key] = file_identity
            last_ms_per_second[second_key] = ms_val
            break
        ms_source = data.get('ms', '')
        ms_to_calc = str(ms_val) if ms_val > 0 else (ms_source if ms_source != "" else "")
        exif_fmt, qt_fmt, keys_val, val, ms_metadata, f_make, f_model, f_json_off, iso_fmt, has_ms = update_media_metadata(
            media_path, dt_base, data['offset'], ms_to_calc, data['extracted_data'])
        (x_tool, x_dt, x_dc_dt, e_dt, e_dto_dt, e_ot, e_sst, 
         q_dt, q_track_dt, q_media_dt, k_dt, make, model) = data['extracted_data']
        dt_name_utc = dt_base
        if val:
            match = re.match(r'([+-])(\d{2}):(\d{2})', val)
            if match:
                sign, hh, mm = match.groups()
                delta = timedelta(hours=int(hh), minutes=int(mm))
                dt_name_utc = dt_base + (delta if sign == '-' else -delta)
        ms_filename = str(ms_val).zfill(3)
        final_base = f"{dt_name_utc.strftime('%Y%m%d_%H%M%S')}{ms_filename}{data['suffix']}"
        cmd_clean = ['exiftool', '-overwrite_original', '-P', '-m', '-api', 'LargeFileSupport=1']
        CLEANUP_TAGS = [
            '-XMP:XMPToolkit=',
            '-XMP:DateCreated=', '-XMP:CreateDate=', '-XMP:ModifyDate=',
            '-EXIF:DateTimeOriginal=', '-EXIF:CreateDate=', '-EXIF:ModifyDate=',
            '-EXIF:OffsetTimeOriginal=', '-EXIF:OffsetTimeDigitized=', '-EXIF:OffsetTime=',
            '-EXIF:SubSecTimeOriginal=', '-EXIF:SubSecTimeDigitized=', '-EXIF:SubSecTime=',
            '-QuickTime:CreateDate=', '-QuickTime:ModifyDate=',
            '-QuickTime:TrackCreateDate=', '-QuickTime:TrackModifyDate=',
            '-QuickTime:MediaCreateDate=', '-QuickTime:MediaModifyDate=',
            '-Keys:CreationDate=']
        subprocess.run(cmd_clean + CLEANUP_TAGS + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#        # ==========================================================
#        # 🔎 WRITE DEBUG (TAKEOUT-SYNC)
#        # ==========================================================
#        print(f"\n--- [DEBUG DE ESCRITURA: {final_base}] ---")
#        w_tool = x_tool if x_tool else ""
#        w_x_dt = f"{exif_fmt}.{ms_metadata}{val}" if x_dt else ""
#        w_x_dc = f"{exif_fmt}.{ms_metadata}{val}" if x_dc_dt else ""
#        w_e_dt = exif_fmt if e_dt else ""
#        w_e_dto = exif_fmt if e_dto_dt else ""
#        w_e_ot = val if e_ot else ""
#        w_e_sst = ms_metadata if e_sst else ""
#        w_q_dt = qt_fmt if q_dt else ""
#        w_q_tr = qt_fmt if q_track_dt else ""
#        w_q_me = qt_fmt if q_media_dt else ""
#        w_k_dt = iso_fmt
#        print(f"XMP Tool:    '{w_tool}'")
#        print(f"XMP Date:    '{w_x_dt}'")
#        print(f"XMP Create:  '{w_x_dc}'")
#        print(f"EXIF Date:   '{w_e_dt}'")
#        print(f"EXIF Orig:   '{w_e_dto}'")
#        print(f"EXIF Offset: '{w_e_ot}'")
#        print(f"EXIF SubSec: '{w_e_sst}'")
#        print(f"QT Date:     '{w_q_dt}'")
#        print(f"QT Track:    '{w_q_tr}'")
#        print(f"QT Media:    '{w_q_me}'")
#        print(f"Keys Apple:  '{w_k_dt}'")
#        print("-" * 40)
#        # ==========================================================
        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-api', 'LargeFileSupport=1', '-api', 'xmp-write=None',
               '-unsafe', '-tagsFromFile', '@', '-MakerNotes']
        cmd += [f'-FileCreateDate#={exif_fmt}.{ms_metadata}{val}', f'-FileModifyDate#={exif_fmt}.{ms_metadata}{val}']
        if geo_payload: 
            cmd += geo_payload
        if x_tool: 
            cmd += [f'-XMP-x:XMPToolkit={x_tool}']
        if x_dc_dt:
            cmd += [f'-XMP-photoshop:DateCreated={exif_fmt}.{ms_metadata}{val}']
        if x_dt:
            cmd += [f'-XMP-xmp:CreateDate={exif_fmt}.{ms_metadata}{val}', f'-XMP-xmp:ModifyDate={exif_fmt}.{ms_metadata}{val}']
        if e_dto_dt:
            cmd += [f'-ExifIFD:DateTimeOriginal={exif_fmt}']
        if e_dt:
            cmd += [f'-ExifIFD:CreateDate={exif_fmt}', f'-ExifIFD:ModifyDate={exif_fmt}']
        if e_ot:
            cmd += [f'-ExifIFD:OffsetTimeOriginal={val}', f'-ExifIFD:OffsetTimeDigitized={val}', f'-ExifIFD:OffsetTime={val}']
        if e_sst:
            cmd += [f'-ExifIFD:SubSecTimeOriginal={ms_metadata}', f'-ExifIFD:SubSecTimeDigitized={ms_metadata}', f'-ExifIFD:SubSecTime={ms_metadata}']
        if data['is_video']:
            if q_dt:
                cmd += [f'-QuickTime:CreateDate={qt_fmt}', f'-QuickTime:ModifyDate={qt_fmt}']
            if q_track_dt:
                cmd += [f'-QuickTime:TrackCreateDate={qt_fmt}', f'-QuickTime:TrackModifyDate={qt_fmt}']
            if q_media_dt:
                cmd += [f'-QuickTime:MediaCreateDate={qt_fmt}', f'-QuickTime:MediaModifyDate={qt_fmt}']
            cmd += [f'-Keys:CreationDate={iso_fmt}']
        subprocess.run(cmd + [media_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _, ext_orig_raw = os.path.splitext(data['orig_name'])
        ext = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}.get(ext_orig_raw.lower(), ext_orig_raw.lower())
        dest_dir = os.path.join(abs_folder, dt_base.strftime("%Y"), dt_base.strftime("%m"))
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"{final_base}{ext}")
        c = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{final_base}_{c}{ext}")
            c += 1
        shutil.move(media_path, dest_path)
        if data['json']:
            orig = data['json']
            ms_int = int(ms_filename or 0)
            ts_utc = dt_base
            if val:
                match = re.match(r'([+-])(\d{2}):(\d{2})', val)
                if match:
                    sign, hh, mm = match.groups()
                    delta = timedelta(hours=int(hh), minutes=int(mm))
                    ts_utc = dt_base + (delta if sign == '-' else -delta)
            ts_millis = str(int(ts_utc.replace(tzinfo=timezone.utc).timestamp() * 1000) + ms_int)
            if not has_ms and ts_millis.endswith("000"):
                ts_millis = ts_millis[:-3]
            ms_suffix = f".{ms_metadata}" if has_ms else ""
            fmt_str = dt_base.strftime("%d %b %Y %H:%M:%S") + f"{ms_suffix} {f_json_off}"
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
            new_json_path = dest_path + ".json"
            with open(new_json_path, 'w', encoding='utf-8') as fj:
                json.dump(new_json, fj, indent=2, ensure_ascii=False)
            if data['json_orig_path'] and os.path.exists(data['json_orig_path']):
                os.remove(data['json_orig_path'])
        print(f"✅ {data['orig_name']} -> {os.path.relpath(dest_path, abs_folder)} (tz: {val})")
    print("\n" + "="*40 + f"\n🚀 PROCESS COMPLETED\n📸 Photos: {photo_count}\n🎥 Videos: {video_count}\n" + "="*40)
if __name__ == "__main__":
    process_master(base_directory)
