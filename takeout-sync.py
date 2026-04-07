import os
import json
import subprocess
import re
import shutil
from datetime import datetime, timezone, timedelta

# --- CONFIGURACIÓN ---
directorio_base = '.'
EXT_VIDEOS = ('.mp4', '.m4v', '.mov', '.3gp')
EXT_FOTOS = ('.jpg', '.jpeg', '.png', '.heic', '.tif', '.tiff', '.webp', '.gif')

# --- BIBLIOTECA DE PLATAFORMAS ---
MAPEO_PLATAFORMAS = {
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

def extraer_ms_de_texto(texto):
    if not texto: return None
    match = re.search(r'[.,](\d{1,3})', texto)
    return match.group(1).ljust(3, '0')[:3] if match else None

def detectar_sufijo_final(make, model, fecha_dt, d_json):
    full_info = f"{make or ''} {model or ''}".lower()
    if 'nokia' in full_info:
        if 'lumia' in full_info: return "_WinPhone"
        es_modelo_android = re.search(r'nokia [1-9](\.[1-9])?|nokia [gcx][0-9]', full_info)
        if es_modelo_android or (fecha_dt and fecha_dt.year >= 2017): return "_Android"
        return "_Symbian"
    for clave, sufijo in MAPEO_PLATAFORMAS.items():
        if clave in full_info: return f"_{sufijo}"
    if d_json and 'deviceType' in d_json:
        dtype = d_json['deviceType'].upper()
        if dtype == 'IOS_PHONE': return "_iOS"
        if dtype == 'ANDROID_PHONE': return "_Android"
    return ""

def obtener_info_exif(ruta_media):
    try:
        cmd = ['exiftool', '-s3', '-d', '%Y:%m:%d %H:%M:%S',
               '-DateTimeOriginal', '-SubSecTimeOriginal', '-Make', '-Model', ruta_media]
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().splitlines()
        dt_str = res[0].strip() if len(res) > 0 else None
        ms_str = res[1].strip() if len(res) > 1 else "000"
        make = res[2].strip() if len(res) > 2 else ""
        model = res[3].strip() if len(res) > 3 else ""
        dt_obj = None
        if dt_str:
            dt_obj = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt_obj, ms_str[:3].ljust(3, '0'), make, model
    except: pass
    return None, "000", "", ""

def detectar_tags_existentes(ruta):
    encontrados = []
    tags_a_buscar = ['TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate']
    try:
        cmd = ['exiftool', '-s', '-m'] + [f'-{t}' for t in tags_a_buscar] + [ruta]
        salida = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
        for t in tags_a_buscar:
            if t.lower() in salida: encontrados.append(t)
    except: pass
    return encontrados

def procesar_maestro(ruta_carpeta):
    archivos_lista = sorted(os.listdir(ruta_carpeta))
    coleccion = {}
    fotos_ok = 0
    videos_ok = 0

    # --- PASO 1: RECOLECCIÓN ---
    for archivo in archivos_lista:
        n_base, ext_raw = os.path.splitext(archivo)
        ext = ext_raw.lower()
        if ext not in EXT_FOTOS and ext not in EXT_VIDEOS: continue
        ruta_m = os.path.join(ruta_carpeta, archivo)
        dt_exif, ms_exif, make, model = obtener_info_exif(ruta_m)
        posibles = [ruta_m + ".json", os.path.join(ruta_carpeta, n_base + ".json")]
        if ext in EXT_VIDEOS:
            for ef in EXT_FOTOS: posibles.append(os.path.join(ruta_carpeta, n_base + ef + ".json"))
        jsons_reales = [p for p in posibles if os.path.exists(p)]
        d_json = None
        if jsons_reales:
            try:
                with open(jsons_reales[0], 'r', encoding='utf-8') as f: d_json = json.load(f)
            except: pass
        sufijo = detectar_sufijo_final(make, model, dt_exif, d_json)
        ts, ms = None, "000"
        if dt_exif:
            ts, ms = str(int(dt_exif.timestamp())), ms_exif
        elif d_json:
            ts = d_json['photoTakenTime']['timestamp']
            ms = extraer_ms_de_texto(d_json['photoTakenTime'].get('formatted', '')) or "000"
        coleccion[archivo.lower()] = {
            'nombre_orig': archivo, 'ts': ts, 'ms': ms, 'json': d_json,
            'jsons_borrar': jsons_reales, 'es_video': ext in EXT_VIDEOS,
            'n_base': n_base.lower(), 'sufijo': sufijo
        }

    # --- PASO 2: SINCRONIZACIÓN ---
    dict_fotos = {v['n_base']: k for k, v in coleccion.items() if not v['es_video'] and v['ts']}
    for k, datos in coleccion.items():
        if datos['es_video']:
            clave_f = dict_fotos.get(datos['n_base'])
            if clave_f:
                f_ref = coleccion[clave_f]
                datos['ts'], datos['ms'] = f_ref['ts'], f_ref['ms']
                datos['sufijo'] = f_ref['sufijo']
                if not datos['json']: datos['json'] = f_ref['json']

    # --- PASO 3: PROCESAMIENTO ---
    tiempos_ocupados = {}
    offsets_rafagas = {}

    for k in sorted(coleccion.keys()):
        datos = coleccion[k]
        if not datos['ts']: continue
        archivo = datos['nombre_orig']
        n_base, ext = os.path.splitext(archivo)
        ruta_m = os.path.join(ruta_carpeta, archivo)
        dt_base = datetime.fromtimestamp(int(datos['ts']), tz=timezone.utc)
        ms_base = datos['ms']

        clave_t = dt_base.strftime("%Y%m%d_%H%M%S") + ms_base
        if clave_t in tiempos_ocupados:
            if tiempos_ocupados[clave_t] == n_base.lower(): ms_desp = 0
            else:
                offsets_rafagas[clave_t] = offsets_rafagas.get(clave_t, 0) + 10
                ms_desp = offsets_rafagas[clave_t]
        else:
            tiempos_ocupados[clave_t] = n_base.lower()
            ms_desp = 0

        dt_f = dt_base + timedelta(milliseconds=ms_desp)
        f_exif, ms_f = dt_f.strftime("%Y:%m:%d %H:%M:%S"), (ms_base if ms_desp == 0 else str(dt_f.microsecond // 1000).zfill(3))

        # --- EXIFTOOL ---
        cmd = ['exiftool', '-overwrite_original', '-P', '-m', '-n', '-api', 'LargeFileSupport=1', '-api', 'ignoreMinorErrors=1']
        if datos['json'] and datos['json'].get('geoData', {}).get('latitude', 0.0) != 0.0:
            geo = datos['json']['geoData']
            cmd += [f'-GPSLatitude={geo["latitude"]}', f'-GPSLongitude={geo["longitude"]}', f'-GPSAltitude={geo.get("altitude", 0.0)}']
        if datos['es_video']:
            tags_v = detectar_tags_existentes(ruta_m)
            cmd += [f'-FileCreateDate={f_exif}', f'-FileModifyDate={f_exif}', f'-CreateDate={f_exif}', f'-ModifyDate={f_exif}',
                    f'-CreationDate={f_exif}.{ms_f}', '-UserData:DateTimeOriginal=', '-XMP:all=']
            for t in tags_v: cmd.append(f'-{t}={f_exif}')
        else:
            cmd += [f'-FileCreateDate={f_exif}', f'-FileModifyDate={f_exif}', f'-CreateDate={f_exif}', f'-ModifyDate={f_exif}',
                    f'-DateTimeOriginal={f_exif}', f'-SubSecTimeOriginal={ms_f}']
        subprocess.run(cmd + [ruta_m], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # --- RENOMBRADO COHERENTE DE EXTENSIONES ---
        ext_orig = ext.lower()
        mapeo_ext = {'.jpeg': '.jpg', '.tiff': '.tif', '.m4v': '.mp4'}
        ext_final = mapeo_ext.get(ext_orig, ext_orig)

        # --- MOVER Y RENOMBRAR ---
        anio_str, mes_str = dt_f.strftime("%Y"), dt_f.strftime("%m")
        dest = os.path.join(ruta_carpeta, anio_str, mes_str)
        os.makedirs(dest, exist_ok=True)
        n_final_base = dt_f.strftime("%Y%m%d_%H%M%S") + ms_f + datos['sufijo']
        ruta_dest = os.path.join(dest, n_final_base + ext_final)

        c = 1
        while os.path.exists(ruta_dest):
            ruta_dest = os.path.join(dest, f"{n_final_base}_{c}{ext_final}")
            c += 1
        shutil.move(ruta_m, ruta_dest)

        # GENERACIÓN DEL JSON (Con extensión y título actualizados)
        if datos['json']:
            d_j = datos['json'].copy()
            d_j['title'] = os.path.basename(ruta_dest)
            d_j['photoTakenTime']['timestamp'] = str(int(dt_f.timestamp()))
            d_j['photoTakenTime']['formatted'] = dt_f.strftime("%d %b %Y %H:%M:%S") + f".{ms_f} UTC"
            with open(ruta_dest + ".json", 'w', encoding='utf-8') as f: json.dump(d_j, f, indent=2)

        for jb in datos['jsons_borrar']:
            if os.path.exists(jb):
                try: os.remove(jb)
                except: pass

        if datos['es_video']: videos_ok += 1
        else: fotos_ok += 1
        print(f"✅ {archivo} -> {anio_str}/{mes_str}/{os.path.basename(ruta_dest)}")

    print("\n" + "="*40 + f"\n🚀 PROCESO FINALIZADO\n📸 Fotos: {fotos_ok}\n🎥 Videos: {videos_ok}\n" + "="*40)

if __name__ == "__main__":
    procesar_maestro(directorio_base)
