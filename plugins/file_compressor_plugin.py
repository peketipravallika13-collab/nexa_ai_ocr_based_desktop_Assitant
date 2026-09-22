"""
File Compressor Plugin for Nexa AI (No API Key Required)
-------------------------------------------------------
Compresses files and directories into ZIP or TAR archives, extracts existing
archives, inspects contents, and reports storage savings completely offline.
"""

import os
import zipfile
import tarfile
import logging
from datetime import datetime

logger = logging.getLogger("file_compressor_plugin")

PLUGIN_SCHEMA = {
    "name": "file_compressor",
    "description": "Compress files/folders into ZIP archives, extract/unzip archives, list archive contents, and check compression stats without any API key.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'compress' (or 'zip'), 'extract' (or 'unzip'), 'list' (view files inside archive), or 'info'."
            },
            "source_path": {
                "type": "STRING",
                "description": "Path to the file, folder, or archive to process (e.g. 'C:/Users/.../Documents/my_folder' or 'data.zip')."
            },
            "destination_path": {
                "type": "STRING",
                "description": "Optional destination path for the output archive or extraction folder. If omitted, creates archive/folder in the same directory."
            },
            "format": {
                "type": "STRING",
                "description": "Archive format: 'zip' (default), 'tar', 'tar.gz', or 'tar.bz2'."
            }
        },
        "required": ["action", "source_path"]
    }
}


def _format_size(size_bytes: int) -> str:
    """Format bytes into readable units."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.2f} MB"
    else:
        return f"{size_bytes / (1024**3):.2f} GB"


def _compress_to_zip(source: str, destination: str) -> str:
    """Compress a file or folder into a ZIP archive."""
    total_uncompressed = 0
    file_count = 0
    
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        if os.path.isfile(source):
            arcname = os.path.basename(source)
            zipf.write(source, arcname=arcname)
            total_uncompressed += os.path.getsize(source)
            file_count = 1
        elif os.path.isdir(source):
            base_dir = os.path.basename(os.path.normpath(source))
            for root, _, files in os.walk(source):
                for f in files:
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, start=os.path.dirname(source))
                    zipf.write(file_path, arcname=rel_path)
                    total_uncompressed += os.path.getsize(file_path)
                    file_count += 1

    compressed_size = os.path.getsize(destination)
    saved_bytes = total_uncompressed - compressed_size
    ratio = (1 - (compressed_size / total_uncompressed)) * 100 if total_uncompressed > 0 else 0
    
    return (
        f"🗜️ **Compression Successful!**\n\n"
        f"- **Archive Created:** `{destination}`\n"
        f"- **Files Included:** `{file_count}`\n"
        f"- **Original Size:** `{_format_size(total_uncompressed)}`\n"
        f"- **Compressed Size:** `{_format_size(compressed_size)}`\n"
        f"- **Space Saved:** `{_format_size(max(0, saved_bytes))}` ({max(0, ratio):.1f}% reduction)\n"
        f"- **Status:** Ready for sharing and storage."
    )


def _compress_to_tar(source: str, destination: str, mode: str = "w:gz") -> str:
    """Compress a file or folder into a TAR / TAR.GZ archive."""
    total_uncompressed = 0
    file_count = 0
    
    with tarfile.open(destination, mode) as tar:
        if os.path.isfile(source):
            tar.add(source, arcname=os.path.basename(source))
            total_uncompressed += os.path.getsize(source)
            file_count = 1
        elif os.path.isdir(source):
            for root, _, files in os.walk(source):
                for f in files:
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, start=os.path.dirname(source))
                    tar.add(file_path, arcname=rel_path)
                    total_uncompressed += os.path.getsize(file_path)
                    file_count += 1

    compressed_size = os.path.getsize(destination)
    saved_bytes = total_uncompressed - compressed_size
    ratio = (1 - (compressed_size / total_uncompressed)) * 100 if total_uncompressed > 0 else 0
    
    return (
        f"🗜️ **Tarball Archive Successful!**\n\n"
        f"- **Archive Created:** `{destination}`\n"
        f"- **Files Included:** `{file_count}`\n"
        f"- **Original Size:** `{_format_size(total_uncompressed)}`\n"
        f"- **Compressed Size:** `{_format_size(compressed_size)}`\n"
        f"- **Space Saved:** `{_format_size(max(0, saved_bytes))}` ({max(0, ratio):.1f}% reduction)"
    )


def _extract_archive(archive_path: str, dest_dir: str) -> str:
    """Extract a ZIP or TAR archive safely."""
    os.makedirs(dest_dir, exist_ok=True)
    
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            # Check for zip bomb / malicious paths
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if not filename and member.endswith('/'):
                    continue
                target_path = os.path.abspath(os.path.join(dest_dir, member))
                if not target_path.startswith(os.path.abspath(dest_dir)):
                    return "Error: Archive contains unsafe directory path traversals."
            zip_ref.extractall(dest_dir)
            file_list = zip_ref.namelist()
            return (
                f"📂 **ZIP Extraction Complete!**\n\n"
                f"- **Source Archive:** `{archive_path}`\n"
                f"- **Extracted To:** `{dest_dir}`\n"
                f"- **Total Files Extracted:** `{len(file_list)}`"
            )
            
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            tar_ref.extractall(dest_dir)
            members = tar_ref.getnames()
            return (
                f"📂 **TAR Extraction Complete!**\n\n"
                f"- **Source Archive:** `{archive_path}`\n"
                f"- **Extracted To:** `{dest_dir}`\n"
                f"- **Total Files Extracted:** `{len(members)}`"
            )
    else:
        return f"Error: File `{archive_path}` is not a recognized ZIP or TAR archive."


def _list_archive_contents(archive_path: str) -> str:
    """List files, sizes, and timestamps inside an archive."""
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            infolist = zip_ref.infolist()
            if not infolist:
                return f"Archive `{archive_path}` is empty."
                
            total_size = sum(info.file_size for info in infolist)
            total_compressed = sum(info.compress_size for info in infolist)
            
            lines = [f"📦 **Archive Contents for `{os.path.basename(archive_path)}`:**\n"]
            lines.append(f"Total Files: **{len(infolist)}** | Total Uncompressed: **{_format_size(total_size)}** | Compressed: **{_format_size(total_compressed)}**\n")
            lines.append("| Filename | Size | Compressed | Modified |")
            lines.append("| :--- | :--- | :--- | :--- |")
            
            # Show up to 25 files
            for info in infolist[:25]:
                dt = datetime(*info.date_time).strftime("%Y-%m-%d %H:%M")
                lines.append(f"| `{info.filename}` | {_format_size(info.file_size)} | {_format_size(info.compress_size)} | {dt} |")
                
            if len(infolist) > 25:
                lines.append(f"\n*...and {len(infolist) - 25} more files.*")
                
            return "\n".join(lines)
            
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            members = tar_ref.getmembers()
            lines = [f"📦 **TAR Archive Contents for `{os.path.basename(archive_path)}`:**\n"]
            lines.append(f"Total Files: **{len(members)}**\n")
            lines.append("| Filename | Size | Modified |")
            lines.append("| :--- | :--- | :--- |")
            for m in members[:25]:
                dt = datetime.fromtimestamp(m.mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"| `{m.name}` | {_format_size(m.size)} | {dt} |")
            if len(members) > 25:
                lines.append(f"\n*...and {len(members) - 25} more files.*")
            return "\n".join(lines)
    else:
        return f"Error: `{archive_path}` is not a valid archive file."


def run(action: str = "compress", source_path: str = "", destination_path: str = "", format: str = "zip") -> str:
    """Main execution point for File Compressor plugin."""
    if not source_path:
        return "Error: No source path provided."
        
    action_clean = action.lower().strip()
    source_clean = os.path.expanduser(source_path.strip().strip('"').strip("'"))
    
    if not os.path.exists(source_clean):
        return f"Error: Source path does not exist at '{source_clean}'."
        
    fmt = (format or "zip").lower().strip()
    
    # 1. Compress / Zip
    if action_clean in ("compress", "zip", "archive", "pack"):
        if destination_path:
            dest = os.path.expanduser(destination_path.strip().strip('"').strip("'"))
        else:
            base = source_clean.rstrip("\\/")
            if fmt == "zip":
                dest = f"{base}.zip"
            elif fmt in ("tar.gz", "tgz"):
                dest = f"{base}.tar.gz"
            elif fmt in ("tar.bz2", "tbz2"):
                dest = f"{base}.tar.bz2"
            else:
                dest = f"{base}.tar"
                
        try:
            if fmt == "zip":
                return _compress_to_zip(source_clean, dest)
            elif fmt in ("tar.gz", "tgz"):
                return _compress_to_tar(source_clean, dest, mode="w:gz")
            elif fmt in ("tar.bz2", "tbz2"):
                return _compress_to_tar(source_clean, dest, mode="w:bz2")
            else:
                return _compress_to_tar(source_clean, dest, mode="w")
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return f"Error compressing files: {str(e)}"
            
    # 2. Extract / Unzip
    elif action_clean in ("extract", "unzip", "unpack", "decompress"):
        if destination_path:
            dest_dir = os.path.expanduser(destination_path.strip().strip('"').strip("'"))
        else:
            # Default folder next to archive
            dest_dir = os.path.splitext(source_clean)[0]
            if dest_dir.endswith(".tar"):
                dest_dir = os.path.splitext(dest_dir)[0]
                
        try:
            return _extract_archive(source_clean, dest_dir)
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return f"Error extracting archive: {str(e)}"
            
    # 3. List / Info
    elif action_clean in ("list", "info", "view", "inspect"):
        try:
            return _list_archive_contents(source_clean)
        except Exception as e:
            logger.error(f"Archive inspection error: {e}")
            return f"Error reading archive contents: {str(e)}"
            
    else:
        return f"Unknown action '{action}'. Choose from: 'compress', 'extract', or 'list'."
