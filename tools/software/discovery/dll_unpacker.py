import pefile
import argparse
from pathlib import Path


class DLLUnpacker:
    def __init__(self, output_base="output/unpacked_dll"):
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)

    def unpack(self, dll_path):
        print(f"Unpacking {dll_path}...")
        try:
            pe = pefile.PE(dll_path)
            out_dir = self.output_base / Path(dll_path).stem
            out_dir.mkdir(parents=True, exist_ok=True)

            # 1. Extract Version Information
            self._extract_version_info(pe, out_dir)

            # 2. Extract Resources (Icons, Manifests, etc.)
            self._extract_resources(pe, out_dir)

            # 3. List Exports/Imports for API Mapping
            self._extract_symbols(pe, out_dir)

            print(f"Unpacked metadata and resources to {out_dir}")
            return True
        except Exception as e:
            print(f"Failed to unpack DLL: {e}")
            return False

    def _extract_version_info(self, pe, out_dir):
        if hasattr(pe, "VS_FIXEDFILEINFO"):
            info = pe.VS_FIXEDFILEINFO[0]
            with open(out_dir / "version_info.txt", "w") as f:
                f.write(
                    f"File version: {info.FileVersionMS >> 16}.{info.FileVersionMS & 0xFFFF}\n"
                )
                f.write(
                    f"Product version: {info.ProductVersionMS >> 16}.{info.ProductVersionMS & 0xFFFF}\n"
                )

    def _extract_resource_data(
        self, pe, resource_lang, type_name, resource_id, res_dir
    ):
        data = pe.get_data(
            resource_lang.data.struct.OffsetToData, resource_lang.data.struct.Size
        )
        file_name = f"res_{type_name}_{resource_id.id}.bin"
        with open(res_dir / file_name, "wb") as f:
            f.write(data)

    def _extract_resource_entry(self, pe, resource_type, res_dir):
        type_name = pefile.RESOURCE_TYPE.get(resource_type.id, resource_type.id)
        if not hasattr(resource_type, "directory"):
            return
        for resource_id in resource_type.directory.entries:
            if not hasattr(resource_id, "directory"):
                continue
            for resource_lang in resource_id.directory.entries:
                self._extract_resource_data(
                    pe, resource_lang, type_name, resource_id, res_dir
                )

    def _extract_resources(self, pe, out_dir):
        res_dir = out_dir / "resources"
        res_dir.mkdir(exist_ok=True)
        if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
            return
        for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            self._extract_resource_entry(pe, resource_type, res_dir)

    def _extract_exports(self, pe, f):
        f.write("--- EXPORTS ---\n")
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                f.write(
                    f"{exp.name.decode() if exp.name else 'ordinal ' + str(exp.ordinal)}\n"
                )

    def _extract_imports(self, pe, f):
        f.write("\n--- IMPORTS ---\n")
        if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                f.write(f"Library: {entry.dll.decode()}\n")
                for imp in entry.symbols:
                    if imp.name:
                        f.write(f"  {imp.name.decode()}\n")

    def _extract_symbols(self, pe, out_dir):
        with open(out_dir / "api_surface.txt", "w") as f:
            self._extract_exports(pe, f)
            self._extract_imports(pe, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unpack DLL resources and metadata.")
    parser.add_argument("dll", help="Path to the DLL file")
    parser.add_argument("--out", default="output/unpacked_dll", help="Output directory")

    args = parser.parse_args()
    unpacker = DLLUnpacker(args.out)
    unpacker.unpack(args.dll)
