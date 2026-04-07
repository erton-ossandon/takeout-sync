# Takeout Sync
An advanced automation tool designed to reorganize, rename, and repair metadata for photo and video libraries exported from Google Takeout. It ensures a consistent naming convention while preserving or restoring technical details.

## Key Features:
- Intelligent Renaming & Hierarchy: Renames files to a precise YYYYMMDD_HHMMSSms_OS.ext format and organizes them into a hierarchical folder structure by Year and Month.
- Multi-Source Metadata Recovery: Prioritizes EXIF data (via exiftool) but falls back to Google JSON sidecars if metadata is missing (common in shared or compressed media).
- Ecosystem Detection (Platform Suffixes): Automatically detects and appends the source platform suffix (_iOS, _Android, _WinPhone, _BlackBerry, _Symbian) by analyzing camera manufacturers, models, and JSON device type fields.
- Nokia Legacy Support: Includes specific logic to differentiate between the three eras of Nokia: Symbian (Classic), Windows Phone (Lumia), and Android (HMD Global).
- Media Synchronization: Automatically syncs timestamp and platform data from a photo to its corresponding video (e.g., Motion Photos or Live Photos) to ensure pairs stay together.
- Format Normalization: Standardizes legacy or redundant extensions (e.g., .jpeg → .jpg, .tiff → .tif, .m4v → .mp4) across the file system and within the internal JSON metadata tags.
- Burst & Conflict Handling: Manages simultaneous captures (burst photos) by adding millisecond offsets to prevent file name collisions.
- GPS & Metadata Injection: Injects GPS coordinates and creation dates directly into the file's binary headers using exiftool for permanent compatibility with gallery apps.

## Useful links:
**Obtaining Exiftool**
- The original version by Phil Harvey. https://exiftool.org/
