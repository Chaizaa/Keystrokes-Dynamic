# Backup Files

## app.py.bak
- **Created**: December 24, 2025
- **Original Size**: 1386 lines
- **Purpose**: Original monolithic Flask application before Blueprint refactoring
- **Status**: DEPRECATED - Use Blueprint structure (app/ package) instead

## Reason for Backup
All routes and functionality have been migrated to the new Blueprint architecture:
- Routes → `app/blueprints/` (main.py, auth.py, api.py)
- Business logic → `app/utils/keystroke_processor.py`
- Configuration → `config.py`
- Entry point → `run.py`

## Migration Mapping

### Original app.py → New Structure
```
app.py (1386 lines)
├── Route handlers      → app/blueprints/main.py (18 lines)
│                        → app/blueprints/auth.py (27 lines)
│                        → app/blueprints/api.py (320+ lines)
│
├── Business logic      → app/utils/keystroke_processor.py (235 lines)
│   ├── process_web_events()
│   └── assess_sample_quality()
│
├── Database calls      → db.py (unchanged, used by blueprints)
├── Verification logic  → verifier.py (unchanged, used by blueprints)
└── Configuration       → config.py (97 lines, NEW)
```

## Rollback Instructions (If Needed)

### If Blueprint Structure Has Issues:
```bash
# Stop new app
# Ctrl+C if running

# Restore original
Copy-Item app.py.bak app.py -Force

# Run original monolithic app
python app.py
```

### After Confirming Blueprint Works:
```bash
# Once satisfied with Blueprint architecture
# You can safely delete this backup
Remove-Item app.py.bak
```

## Do NOT Modify
This file is a **READ-ONLY BACKUP**. Do not make changes here.
All new development should happen in the Blueprint structure.
