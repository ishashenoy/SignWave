# FlowState Design System

## Overview
This design system is extracted from the results page and provides a cohesive purple/pink/orange neon aesthetic on a dark background.

---

## 🎨 Color Palette

### Background Colors
- **Deep**: `--color-bg-deep` (#06010f) - Darkest background
- **Mid**: `--color-bg-mid` (#0d0420) - Mid-tone background
- **Surface**: `--color-bg-surface` (#1e0a3a) - Surface/panel background

### Text Colors
- **Primary**: `--color-text-primary` (#f0e6ff) - Brightest text
- **Secondary**: `--color-text-secondary` (#d8d0f0) - Regular text
- **Tertiary**: `--color-text-tertiary` (#c4b5fd) - De-emphasized
- **Muted**: `--color-text-muted` - Subtle text (70% opacity)
- **Subtle**: `--color-text-subtle` - Labels (45% opacity)
- **Faint**: `--color-text-faint` - Very subtle (30% opacity)

### Accent Colors
| Color | Variable | Hex | Use Case |
|-------|----------|-----|----------|
| Green | `--color-accent-green` | #86efac | Accuracy, success |
| Blue | `--color-accent-blue` | #a5b4fc | Combos, info |
| Amber | `--color-accent-amber` | #fcd34d | Scores, highlights |
| Rose | `--color-accent-rose` | #fda4af | Misses, errors |

---

## 🌈 Gradients

### Button Gradients
```css
--gradient-primary: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
--gradient-secondary: linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%);
--gradient-tertiary: linear-gradient(135deg, #312e81 0%, #4338ca 100%);
```

### Text Gradients
```css
--gradient-hero: linear-gradient(180deg, #fde68a 0%, #f59e0b 30%, #d946ef 70%, #a855f7 100%);
--gradient-heading: linear-gradient(135deg, #fde68a, #fbbf24, #c4b5fd);
```

---

## 📦 Components

### Buttons

#### Standard Buttons
```html
<a href="#" class="btn btn-primary">Primary</a>
<a href="#" class="btn btn-secondary">Secondary</a>
<a href="#" class="btn btn-tertiary">Tertiary</a>
```

#### Skewed Buttons (Results Style)
```html
<a href="#" class="btn btn-primary btn-skewed">
    <span>Button Text</span>
</a>
```

#### Back Button
```html
<a href="#" class="btn-back">
    <span class="arrow">‹</span>
    <span>Back</span>
</a>
```

---

### Cards

```html
<!-- Primary card -->
<div class="card">
    <h3>Card Title</h3>
    <p>Card content...</p>
</div>

<!-- Secondary card (more subtle) -->
<div class="card-secondary">
    <p>Less prominent content</p>
</div>

<!-- Subtle card (minimal emphasis) -->
<div class="card-subtle">
    <p>Background info</p>
</div>

<!-- Banner (featured content) -->
<div class="banner">
    <span class="label-sm">Label</span>
    <h2>Banner Title</h2>
</div>
```

---

### Statistics

```html
<!-- Stat card -->
<div class="stat-card">
    <span class="stat-label">Accuracy</span>
    <div class="stat-value stat-green">98.5%</div>
</div>

<!-- Available stat colors: stat-green, stat-blue, stat-amber, stat-rose -->

<!-- Hero stat (large percentage) -->
<div class="stat-hero">95.4%</div>
```

---

### Pills & Badges

```html
<div class="pill">
    <span class="pill-dot dot-perfect"></span>
    Perfect 12
</div>

<!-- Available dot types: dot-perfect, dot-good, dot-ok, dot-miss -->
```

---

## 📐 Layout

### Container
```html
<div class="container">
    <!-- Centered content, max-width 1200px -->
</div>

<div class="page-wrapper">
    <!-- Full-height page layout -->
</div>
```

---

## 🔤 Typography

### Headings
```html
<h1>Main Title</h1>           <!-- or class="heading-1" -->
<h2>Section Title</h2>         <!-- or class="heading-2" -->
<h3>Subsection</h3>            <!-- or class="heading-3" -->
<p class="subtitle">Subtitle text</p>
```

### Labels
```html
<span class="label-sm">Small Label</span>
<span class="label-xs">Extra Small Label</span>
```

---

## ✨ Effects

### Glows
All stat accent colors have matching glow effects:
```css
text-shadow: var(--glow-green);
text-shadow: var(--glow-blue);
text-shadow: var(--glow-amber);
text-shadow: var(--glow-rose);
```

### Shadows
```css
box-shadow: var(--shadow-card);  /* For elevated cards */
```

---

## 🎭 Animations

```html
<div class="animate-fadeIn">Fades in</div>
<div class="animate-slideInUp">Slides up</div>
<div class="animate-slideInDown">Slides down</div>
<div class="animate-slideInLeft">Slides from left</div>
<div class="animate-slideInRight">Slides from right</div>
```

---

## 🛠️ Utility Classes

### Flexbox
```html
<div class="flex">                <!-- display: flex -->
<div class="flex flex-col">       <!-- flex-direction: column -->
<div class="flex flex-center">    <!-- center items -->
<div class="flex flex-between">   <!-- space-between -->
```

### Gaps
```html
<div class="flex gap-xs">   <!-- 4px gap -->
<div class="flex gap-sm">   <!-- 8px gap -->
<div class="flex gap-md">   <!-- 12px gap -->
<div class="flex gap-lg">   <!-- 18px gap -->
```

### Spacing
```html
<div class="mt-sm">   <!-- margin-top: 8px -->
<div class="mt-md">   <!-- margin-top: 12px -->
<div class="mt-lg">   <!-- margin-top: 18px -->
<div class="mb-sm">   <!-- margin-bottom: 8px -->
<div class="mb-md">   <!-- margin-bottom: 12px -->
<div class="mb-lg">   <!-- margin-bottom: 18px -->
```

### Text Alignment
```html
<div class="text-center">
<div class="text-left">
<div class="text-right">
```

---

## 📏 Spacing Scale

```css
--spacing-xs: 4px
--spacing-sm: 8px
--spacing-md: 12px
--spacing-lg: 18px
--spacing-xl: 24px
--spacing-2xl: 36px
```

---

## 🔘 Border Radius

```css
--radius-sm: 4px
--radius-md: 6px
--radius-lg: 8px
--radius-xl: 12px
```

---

## ♿ Accessibility

- **Focus states**: Amber outline on keyboard navigation
- **Reduced motion**: Respects `prefers-reduced-motion` setting
- **Color contrast**: All text meets WCAG AA standards on dark backgrounds
- **Semantic HTML**: Use proper heading hierarchy

---

## 📱 Responsive Design

The theme is mobile-responsive out of the box:
- Headings scale down on smaller screens
- Buttons adjust padding
- Container padding reduces
- Stat hero sizes adapt

Breakpoints:
- **768px**: Tablet and below
- **480px**: Mobile

---

## 🎯 Usage Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>FlowState Page</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container animate-fadeIn">
        <h1>FlowState</h1>
        <p class="subtitle">Hand Gesture Rhythm Game</p>
        
        <div class="card">
            <div class="flex gap-md">
                <div class="stat-card">
                    <span class="stat-label">Score</span>
                    <div class="stat-value stat-amber">1,275</div>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Accuracy</span>
                    <div class="stat-value stat-green">65.4%</div>
                </div>
            </div>
        </div>
        
        <div class="flex gap-sm mt-lg" style="justify-content: center;">
            <a href="#" class="btn btn-primary">Play Again</a>
            <a href="#" class="btn btn-secondary">Dashboard</a>
        </div>
    </div>
</body>
</html>
```

---

## 🎨 Visual Effects

### Background Layers
The body automatically includes:
1. **Radial gradient background**: Purple to black
2. **Vignette overlay**: Darkens edges
3. **Noise texture**: Subtle grain effect

These are applied via `body::before` and `body::after` pseudo-elements.

---

## 💡 Tips

1. **Always include Inter font** from Google Fonts for consistency
2. **Use CSS variables** instead of hard-coded colors
3. **Layer z-index properly**: Background layers are z-index: 0, content should be z-index: 1+
4. **Combine utility classes** for rapid development
5. **Test animations** with reduced motion preference enabled
6. **Use semantic HTML** for better accessibility

---

## 📚 Component Hierarchy

```
Typography
├── h1, .heading-1 (Hero titles)
├── h2, .heading-2 (Sections)
├── h3, .heading-3 (Subsections)
├── .subtitle (Descriptions)
├── .label-sm (Small labels)
└── .label-xs (Tiny labels)

Containers
├── .container (Page container)
├── .page-wrapper (Full height)
├── .card (Primary cards)
├── .card-secondary (Secondary cards)
├── .card-subtle (Subtle cards)
└── .banner (Featured content)

Interactive
├── .btn + .btn-primary/secondary/tertiary
├── .btn-skewed (Results style)
└── .btn-back (Navigation)

Data Display
├── .stat-card (Stat container)
├── .stat-value + .stat-green/blue/amber/rose
├── .stat-hero (Large percentage)
└── .pill (Badges)
```

---

## 🚀 Quick Start

1. Link the stylesheet in your HTML:
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
   ```

2. Include Inter font:
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
   ```

3. Use components:
   ```html
   <div class="container">
       <h1>Your Title</h1>
       <div class="card">
           <!-- Your content -->
       </div>
   </div>
   ```

---

## 🔍 Viewing the Component Demo

To see all components in action, navigate to `/components_demo` route (you'll need to add this to your Flask app).

Example Flask route:
```python
@app.route('/components_demo')
def components_demo():
    return render_template('components_demo.html')
```
