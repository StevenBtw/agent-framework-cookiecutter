"""Post-generation hook to clean up files based on cookiecutter choices."""

import os

interface = "{{ cookiecutter.interface }}"
governance_level = "{{ cookiecutter.governance_level }}"

package_dir = os.path.join("src", "{{ cookiecutter.package_name }}")
interfaces_dir = os.path.join(package_dir, "interfaces")
tests_dir = "tests"

# Interfaces ----------------------------------------------------------------
if interface == "cli":
    os.remove(os.path.join(interfaces_dir, "server.py"))
elif interface == "fastapi":
    os.remove(os.path.join(interfaces_dir, "cli.py"))

# Governance ---------------------------------------------------------------
if governance_level == "none":
    for victim in (
        os.path.join(package_dir, "governance.py"),
        "policies.yaml",
        os.path.join(tests_dir, "test_governance.py"),
    ):
        if os.path.exists(victim):
            os.remove(victim)
