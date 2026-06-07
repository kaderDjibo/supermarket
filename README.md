# Supermarket Streamlit App

A local Streamlit app for managing supermarket inventory, sales, suppliers, purchase orders, and customer loans.

## Quick start

1. Open PowerShell in the app folder:
   ```powershell
   cd "C:\Users\H P\Desktop\New folder (5)\supermarket\supermarket_app"
   ```
2. Create and activate the virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate
   ```
3. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install --only-binary=:all: -r requirements.txt
   ```
4. Launch the app:
   ```powershell
   python -m streamlit run app.py --server.port 8505
   ```

## Alternative app launch

Use the helper scripts below from PowerShell:
```powershell
.\run_app.bat
```
```powershell
.\run_app.ps1
```

## App URL

Open `http://localhost:8505` in your browser after the app starts.
