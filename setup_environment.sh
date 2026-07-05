#!/bin/bash
set -e

echo -e "\033[1;36mSetting up KhabriChacha Environment...\033[0m"

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "\033[0;31mERROR: python3 is not installed or not in PATH.\033[0m"
    exit 1
fi

# 2. Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo -e "\033[1;33mCreating virtual environment (.venv)...\033[0m"
    python3 -m venv .venv
else
    echo -e "\033[1;32mVirtual environment already exists.\033[0m"
fi

# 3. Activate Virtual Environment
echo -e "\033[1;33mActivating virtual environment...\033[0m"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo -e "\033[0;31mERROR: Could not find activation script at .venv/bin/activate\033[0m"
    exit 1
fi

# 4. Upgrade pip
echo -e "\033[1;33mUpgrading pip...\033[0m"
python -m pip install --upgrade pip

# 5. Install Requirements
echo -e "\033[1;33mInstalling dependencies from requirements.txt...\033[0m"
pip install -r requirements.txt

# 6. Verify Installation
echo -e "\033[1;33mVerifying installation...\033[0m"
if [ -f "verify_environment.py" ]; then
    python verify_environment.py
else
    echo -e "\033[1;33mverify_environment.py not found. Skipping verification.\033[0m"
fi

echo -e "\n\033[1;32mEnvironment setup complete! Run the app with: python app.py\033[0m"
