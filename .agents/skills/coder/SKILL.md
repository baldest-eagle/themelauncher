---
name: coder
description: Focuses on writing visual interface features, layout components, and critical Windows system interaction logic.
---

# UI Framework Directive: CustomTkinter
All user interface modules, sliders, toggles, and windows generated for this project MUST utilize the `customtkinter` (ctk) library instead of default `tkinter`.

 ## 1. Import and Initialization Standards
Every UI component file must start with the standard import footprint:
```python
import customtkinter as ctk

# Enforce system-wide initial rendering behaviors
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("themes/custom_accent.json")
```M

 ## 2. Structural Window Paradigms
* *+Class Architecture:** All window layouts must inherit cleanly from `ctk.CTk` or `ctk.CTkFrame`.
* **·Sizing Rules:** Utilize grid geometry management configurations (`grid_columnconfigure`, `grid_rowconfigure`) with fractional weightings to support smooth, seamless desktop window resizing.
* **Component Instantiation:** Use modern `ctk` widgets explicitly (`ctk.CTkButton`, `ctk.CTkLabel`, `ctk.CTkSwitch`, `ctk.CTkTabview`). Never mix standard legacy tkinter components into the frame.

## 3. Dynamic Color Morphing Implementation
When coding theme application modules, utilize the live theme engine injection pattern. Ensure buttons or checkboxes trigger configuration updates pointing directly to your local JSON theme payload:
```python
def update_ui_palette(self, target_theme_json_path):
    """Updates the runtime visual theme profile without closing window loops."""
    ctk.set_default_color_theme(target_theme_json_path)
```