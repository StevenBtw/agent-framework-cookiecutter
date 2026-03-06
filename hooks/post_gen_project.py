"""Post-generation hook to clean up files based on cookiecutter choices."""

import os
import shutil

interface = "{{ cookiecutter.interface }}"

interfaces_dir = os.path.join("src", "{{ cookiecutter.package_name }}", "interfaces")

# Remove unused interface files
if interface == "cli":
    os.remove(os.path.join(interfaces_dir, "server.py"))
elif interface == "fastapi":
    os.remove(os.path.join(interfaces_dir, "cli.py"))

# Both keeps all files
