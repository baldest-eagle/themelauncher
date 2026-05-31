---
name: bot-builder
description: Builds automated manifest generation tools and legacy 7TSP-to-Windhawk icon converters.
---

# Automation Blueprints

## Manifest Generation Bot
* Monitor incoming file streams or directories. 
* If a theme folder is detected without a standard configuration layout, auto-generate a baseline template populated with inferred metadata.

## 7TSP to Windhawk Conversion Rules
1. **Extraction Phase:** Unpack the compressed archive into a temporary workspace directory: `/assets/temp_extracted/`.
2. **Resource Re-mapping:** For each `.res` file discovered, strip the extension, replace it with `.dll` formatting, and stage it in the output path.
3. **Manifest Generation (`theme.ini`):** Generate a standard `theme.ini` mapping header mapping the systemic binaries (e.g., `%SystemRoot%\System32\imageres.dll=imageres.dll`).
4. **Directory Staging:** Move assets to `/themes/[ThemeName]/Icons/` and wipe out temporary workspace paths completely.
5. **Intelligent Icon Mapping:** Process standalone `.ico` files using pattern matching to map to DLL/resource indices for Windhawk Resource Redirect.

## Icon Mapping Logic
The `infer_mapping()` method handles:
- Known filenames (computer.ico, folder.ico, network.ico, etc.)
- Pattern-matched variants (JAPAN-area o4_Computer.ico → imageres.dll/109)
- Copies unmapped icons for manual configuration

## Windhawk Resource Redirect Support
- `_apply_icons_windhawk()` deploys icons to `C:\Windhawk\Resources\[ThemeName]\`
- Naming convention: `{dll_name}_{resource_index}.ico` (e.g., `imageres_109.ico`)
- Handles both shortcut icons and system DLL replacement icons
