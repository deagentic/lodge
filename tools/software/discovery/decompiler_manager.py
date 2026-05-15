import subprocess  # nosec B404
import shutil
import argparse
from pathlib import Path


class DecompilerManager:
    def __init__(self, output_base="output/decompiled"):
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)

    def decompile_dotnet(self, file_path):
        """Uses ilspycmd to decompile .NET assemblies (C# and VB.NET)."""
        out_dir = self.output_base / "dotnet" / Path(file_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[.NET] Decompiling {file_path} to {out_dir}...")

        try:
            # ilspycmd supports both C# and VB.NET assemblies; output is always C#
            subprocess.run(["ilspycmd", "-o", str(out_dir), "-p", str(file_path)], check=True)  # nosec B603, B607
            return True
        except FileNotFoundError:
            print("[ERROR] 'ilspycmd' not found. Install with: dotnet tool install -g ilspycmd")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] .NET decompilation failed: {e}")
        return False

    def decompile_java(self, file_path):
        """Uses CFR (primary) or Procyon (fallback) to decompile Java .class/.jar files."""
        out_dir = self.output_base / "java" / Path(file_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Java] Decompiling {file_path} to {out_dir}...")

        cfr_jar = Path("tools/bin/cfr.jar")
        procyon_jar = Path("tools/bin/procyon.jar")

        # Try CFR first (better for modern Java/Kotlin bytecode)
        if cfr_jar.exists():
            try:
                cmd = ["java", "-jar", str(cfr_jar), str(file_path), "--outputdir", str(out_dir)]
                subprocess.run(cmd, check=True)  # nosec B603, B607
                return True
            except subprocess.CalledProcessError as e:
                print(f"[WARN] CFR failed ({e}), trying Procyon fallback...")

        # Procyon fallback (better for older .class files and enum handling)
        if procyon_jar.exists():
            try:
                cmd = ["java", "-jar", str(procyon_jar), "-o", str(out_dir), str(file_path)]
                subprocess.run(cmd, check=True)  # nosec B603, B607
                return True
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Procyon decompilation also failed: {e}")
        else:
            if not cfr_jar.exists():
                print("[ERROR] Neither cfr.jar nor procyon.jar found in tools/bin/. Run setup/install.sh first.")

        return False

    def decompile_python(self, file_path):
        """Decompiles .pyc files. Uses decompyle3 for Python 3.9+ and uncompyle6 for <=3.8."""
        out_file = self.output_base / "python" / (Path(file_path).stem + ".py")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Python] Decompiling {file_path} to {out_file}...")

        # Try decompyle3 first (supports Python 3.9–3.11)
        for tool in ["decompyle3", "uncompyle6"]:
            if shutil.which(tool):
                try:
                    with open(out_file, "w") as f:
                        subprocess.run([tool, str(file_path)], stdout=f, check=True)  # nosec B603, B607
                    print(f"  [OK] Used {tool}")
                    return True
                except subprocess.CalledProcessError:
                    print(f"  [WARN] {tool} failed, trying next decompiler...")

        print("[ERROR] No working .pyc decompiler found. Install with: pip install decompyle3 uncompyle6")
        return False

    def route_file(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext in ['.dll', '.exe']:
            return self.decompile_dotnet(file_path)
        elif ext in ['.class', '.jar']:
            return self.decompile_java(file_path)
        elif ext in ['.pyc']:
            return self.decompile_python(file_path)
        else:
            print(f"[SKIP] No decompiler for {ext} files.")
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decompile binary artifacts for static analysis.")
    parser.add_argument("file", help="Path to the binary file (DLL, JAR, PYC, etc.)")
    parser.add_argument("--out", default="output/decompiled", help="Base output directory")

    args = parser.parse_args()
    manager = DecompilerManager(args.out)
    manager.route_file(args.file)
