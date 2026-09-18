"""
Organiza fotos y vídeos de la carpeta de iCloud Photos en Año / Mes / Día dentro de mi carpeta FOTOS.

Usa ExifTool para leer la fecha real de captura: https://exiftool.org/

Comandos:
  python organizar_fotos.py                  -> organiza de verdad
  python organizar_fotos.py --dry-run         -> solo simula, no mueve nada
  python organizar_fotos.py --copiar          -> copia en vez de mover (deja el original en iCloud Photos)
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ORIGEN_DEFECTO = r"C:\Users\Alfredo\Pictures\iCloud Photos\Photos"
DESTINO_DEFECTO = r"C:\Users\Alfredo\Desktop\FOTOS"

MESES_ES = {
    1: "01 Enero", 2: "02 Febrero", 3: "03 Marzo", 4: "04 Abril",
    5: "05 Mayo", 6: "06 Junio", 7: "07 Julio", 8: "08 Agosto",
    9: "09 Septiembre", 10: "10 Octubre", 11: "11 Noviembre", 12: "12 Diciembre",
}

# Fechas de las fotos en orden de preferencia
CAMPOS_FECHA = [
    "DateTimeOriginal",   # fecha de captura en fotos
    "CreateDate",         # fecha de creación (fotos y algunos vídeos)
    "MediaCreateDate",    # fecha de creación en vídeos (MOV/MP4)
    "TrackCreateDate",
    "FileModifyDate",     # último recurso: fecha de modificación del archivo
]

EXTENSIONES_VALIDAS = {
    ".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".tiff", ".bmp",
    ".mov", ".mp4", ".m4v", ".avi",
}


def comprobar_exiftool():
    try:
        subprocess.run(["exiftool", "-ver"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: no se encuentra ExifTool.")
        sys.exit(1)


def obtener_metadatos(carpeta_origen: Path):
    """Llama a exiftool sobre toda la carpeta y devuelve la lista de metadatos."""
    #Crear el comando para exiftool
    campos = []
    for campo in CAMPOS_FECHA:
        campos += ["-" + campo]
    cmd = ["exiftool", "-j", "-r"] + campos + [str(carpeta_origen)]

    resultado = subprocess.run(cmd, capture_output=True, text=True)

    if resultado.returncode not in (0, 1):  #0 ok, 1 si hay algun warning
        print("ERROR ejecutando exiftool:", resultado.stderr)
        sys.exit(1)
    try:
        return json.loads(resultado.stdout)
    except json.JSONDecodeError:
        print("No se pudieron leer los metadatos (¿carpeta vacía?).")
        return []


def parsear_fecha(valor: str):
    """ExifTool da 'YYYY:MM:DD HH:MM:SS' o con zona horaria al final."""
    if not valor:
        return None
    valor = valor.split("+")[0].split("-0")[0].strip()  # recorta zona horaria si la hay
    formatos = ["%Y:%m:%d %H:%M:%S", "%Y:%m:%d"]
    for fmt in formatos:
        try:
            return datetime.strptime(valor[: len(fmt) + 6].strip(), fmt)
        except ValueError:
            continue
    return None


def fecha_del_archivo(item: dict):
    for campo in CAMPOS_FECHA:
        if campo in item:
            fecha = parsear_fecha(item[campo])
            if fecha:
                return fecha
    return None

def ruta_destino_unica(destino: Path) -> Path:
    """Si ya existe un archivo con ese nombre, añade un sufijo numérico."""
    if not destino.exists():
        return destino
    base, ext = destino.stem, destino.suffix
    contador = 1
    while True:
        candidato = destino.with_name(f"{base}_{contador}{ext}")
        if not candidato.exists():
            return candidato
        contador += 1


def organizar(origen: Path, destino: Path, dry_run: bool, copiar: bool):
    comprobar_exiftool()
    print(f"Leyendo metadatos de: {origen}")
    metadatos = obtener_metadatos(origen)

    total = movidos = sin_fecha = 0

    for item in metadatos:
        ruta_origen = Path(item["SourceFile"])
        if ruta_origen.suffix.lower() not in EXTENSIONES_VALIDAS:
            continue

        total += 1
        fecha = fecha_del_archivo(item)

        if fecha is None:
            sin_fecha += 1
            print(f"  [SIN FECHA] {ruta_origen.name} -> revisar a mano")
            continue

        carpeta_destino = (
            destino / str(fecha.year) / MESES_ES[fecha.month] / f"{fecha.day:02d}"
        )
        ruta_final = ruta_destino_unica(carpeta_destino / ruta_origen.name)

        accion = "COPIAR" if copiar else "MOVER"
        print(f"  [{accion}] {ruta_origen.name} -> {ruta_final.relative_to(destino)}")

        if not dry_run:
            carpeta_destino.mkdir(parents=True, exist_ok=True)
            if copiar:
                shutil.copy2(ruta_origen, ruta_final)
            else:
                shutil.move(str(ruta_origen), str(ruta_final))
            movidos += 1

    print("\n--- Resumen ---")
    print(f"Archivos encontrados: {total}")
    if dry_run:
        print("Modo simulación (--dry-run): no se ha movido nada de verdad.")
    else:
        print(f"Archivos organizados: {movidos}")
    if sin_fecha:
        print(f"Archivos sin fecha detectable: {sin_fecha} (quedaron en su sitio original)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organiza fotos/vídeos por Año/Mes/Día")
    parser.add_argument("--origen", default=ORIGEN_DEFECTO, help="Carpeta de iCloud Photos")
    parser.add_argument("--destino", default=DESTINO_DEFECTO, help="Carpeta FOTOS")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin mover archivos")
    parser.add_argument("--copiar", action="store_true", help="Copia en vez de mover")
    args = parser.parse_args()

    organizar(Path(args.origen), Path(args.destino), args.dry_run, args.copiar)
