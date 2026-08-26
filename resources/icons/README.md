# PyMeOS Icons

This directory contains SVG icons for PyMeOS, designed to provide a modern and consistent look across the application.

## Icon Set

All icons are based on **Material Symbols** (Google) and **Feather Icons**, optimized for high-DPI displays.

### Categories

| Category       | Icons | Description                          |
|----------------|-------|--------------------------------------|
| **General**    | 10    | New, Open, Save, etc.                |
| **Competition**| 8     | Runner, Team, Class, Course, etc.    |
| **SI Reader**  | 6     | USB, Card, Refresh, etc.             |
| **Status**     | 6     | OK, DNF, DNS, DQ, MP, Warning         |
| **Actions**    | 12    | Add, Edit, Delete, Import, Export, etc.|

### Usage

In Qt/PySide6, load icons like this:

```python
from PySide6.QtGui import QIcon

# Load from file
icon = QIcon("resources/icons/new.svg")
button.setIcon(icon)

# Or use resource system (recommended)
icon = QIcon(":/icons/new.svg")
```

### Color Customization

All icons use `currentColor` for fill/stroke, which inherits the widget's text color. To customize:

```css
/* In your QSS file */
QPushButton {
    color: #3b82f6; /* Icon will use this color */
}
```

### Adding New Icons

1. Use [Material Symbols](https://fonts.google.com/icons) or [Feather Icons](https://feathericons.com/)
2. Export as SVG (24x24px, no fill, stroke="currentColor")
3. Optimize with [SVGO](https://jakearchibald.github.io/svgomg/)
4. Place in the appropriate subdirectory

## License

Icons are derived from open-source projects:
- [Material Symbols](https://github.com/google/material-design-icons) (Apache 2.0)
- [Feather Icons](https://github.com/feathericons/feather) (MIT)

All icons in this directory are released under the **MIT License**.
