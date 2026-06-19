# LuxCode Desktop

Tkinter tabanli LuxCode Desktop istemcisi.

## Baslatma

```powershell
python run_desktop.py
```

Backend varsayilani:

```text
http://127.0.0.1:5000
```

## Mimari

Desktop uygulama dogrudan model API cagirmaz, ana repository dosyalarina otomatik kod yazmaz, otomatik commit/push yapmaz.

Akis:

```text
LuxCode Desktop UI
-> LUXDEEP HTTP API / Local Bridge
-> Task Orchestrator
-> Model Router
-> Permission System
-> Safe Patch / Validation / Integration
```

Backend yoksa UI `BACKEND CONNECTION REQUIRED` gosterir.

## Panel Duzeni

Sol panel sekmeleri:

```text
Files, Models, Tasks, Workspace
```

Orta alan sekmeleri:

```text
Workspace, Task Plan, Repository Settings, Settings, Safe Patch, Validation, History
```

Sag panel sekmeleri:

```text
Plan, Diagnostics, Permissions, Safe Patch, Validation, Integration, Evidence
```

Sol ve sag paneller `PanedWindow` ile yeniden boyutlandirilabilir, gizlenebilir ve tekrar acilabilir.

## Guvenlik Sinirlari

- UI icinden dogrudan provider API cagrisi yok.
- API key UI icinde saklanmaz.
- Safe Patch onayi olmadan apply yok.
- Auto apply varsayilan kapali.
- Paid escalation varsayilan kapali.
- Commit/push otomatik yok.
- Polling sadece durum okur.

## Test

```powershell
python -m unittest discover luxcode_desktop/tests
```
