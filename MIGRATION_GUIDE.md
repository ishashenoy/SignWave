# Migration Guide: Applying FlowState Design System

## Quick Start

The global theme has been extracted and is ready to use. Here's how to apply it to your pages.

---

## ✅ Already Updated

- **style.css** → Complete design system with CSS variables
- **index.html** → Updated to use Inter font and animation classes
- **results.html** → Source of the design system (no changes needed)

---

## 📋 Pages to Migrate

### 1. home.html
**Current**: Custom embedded styles with purple/gold theme  
**Action**: Replace embedded styles with global theme

**Before** (embedded `<style>` block):
```html
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Inter', ...;
        background: #07030f;
        ...
    }
</style>
```

**After** (use global stylesheet):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```

**Color Replacement Map**:
```css
/* Replace these custom colors with CSS variables */
#07030f → var(--color-bg-deep)
#130a28 → var(--color-bg-mid)
rgba(100, 50, 180, 0.18) → var(--bg-card-primary)
rgba(250, 204, 21, ...) → var(--color-accent-amber)
```

---

### 2. song_selection.html
**Current**: Custom embedded styles, similar to home.html  
**Action**: Same as home.html - replace with global theme

**Button Migration Example**:
```html
<!-- Before: Custom button -->
<a href="#" style="background: linear-gradient(...)">Play</a>

<!-- After: Use theme button -->
<a href="#" class="btn btn-primary">Play</a>
```

---

### 3. dashboard.html
**Current**: Partially aligned with purple theme  
**Action**: Replace inline gradients with CSS variables

**Example Replacements**:
```css
/* Before */
background: linear-gradient(135deg, rgba(120, 80, 200, 0.12), rgba(250, 204, 21, 0.03));

/* After */
background: var(--bg-card-primary);
border: 1px solid var(--border-primary);
```

---

### 4. calibrate.html, freestyle.html, game.html
Check these pages and apply similar migrations.

---

## 🔧 Step-by-Step Migration Process

### Step 1: Add Font & Stylesheet
Replace any embedded `<style>` blocks header with:
```html
<head>
    ...
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    
    <!-- Page-specific styles can go here if needed -->
    <style>
        /* Only unique layout styles for this page */
    </style>
</head>
```

### Step 2: Replace Colors
Use find & replace to swap hard-coded colors with CSS variables:

| Find | Replace With |
|------|--------------|
| `#07030f` | `var(--color-bg-deep)` |
| `#0d0420` | `var(--color-bg-mid)` |
| `#1e0a3a` | `var(--color-bg-surface)` |
| `#ffffff`, `#fff` | `var(--color-text-primary)` |
| `rgba(255, 255, 255, 0.6)` | `var(--color-text-muted)` |

### Step 3: Use Component Classes
Replace custom button/card styles with theme classes:

```html
<!-- Cards -->
<div style="background: rgba(40, 10, 80, 0.3); border: ...">
    → <div class="card-secondary">

<!-- Buttons -->
<a style="background: linear-gradient(...); padding: ...">
    → <a class="btn btn-primary">

<!-- Stats -->
<div style="font-size: 2rem; font-weight: 900; color: #86efac;">
    → <div class="stat-value stat-green">
```

### Step 4: Add Animations
Enhance page load with animations:
```html
<div class="container animate-fadeIn">
<div class="hero-section animate-slideInLeft">
<div class="action-buttons animate-slideInUp">
```

### Step 5: Test Responsiveness
The global theme includes responsive breakpoints. Test on:
- Desktop (1920px)
- Tablet (768px)
- Mobile (480px)

---

## 🎨 CSS Variable Reference

### Common Replacements

| Old Style | CSS Variable |
|-----------|--------------|
| Background colors | `--color-bg-deep/mid/surface` |
| Text colors | `--color-text-primary/secondary/tertiary` |
| Purple gradients | `--gradient-primary/secondary/tertiary` |
| Gold gradient | `--gradient-heading` |
| Card backgrounds | `--bg-card-primary/secondary/subtle` |
| Borders | `--border-primary/secondary/subtle` |
| Border radius | `--radius-sm/md/lg/xl` |
| Spacing | `--spacing-xs/sm/md/lg/xl` |

---

## 📝 Home.html Migration Example

### Before (lines 14-21):
```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', ...;
    background: #07030f;
    min-height: 100vh;
    overflow: hidden;
    color: #ffffff;
    -webkit-font-smoothing: antialiased;
    position: relative;
}
```

### After:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```
*(Body styles now inherited from global theme)*

### Custom Page Styles Kept:
```html
<style>
    /* Keep unique animations specific to home.html */
    .orb {
        position: absolute;
        border-radius: 50%;
        filter: blur(80px);
        animation: orbFloat linear infinite;
    }
    
    /* Layout specific to home page */
    .hero-content {
        /* custom layout */
    }
</style>
```

---

## 🚫 What NOT to Change

Keep these page-specific items:
- ✅ Unique layout structures (grid, flex containers)
- ✅ Custom animations not in global theme
- ✅ Page-specific JavaScript
- ✅ SVG graphics and icons
- ✅ Canvas elements

Only replace:
- ❌ Colors (use CSS variables)
- ❌ Fonts (use Inter from global)
- ❌ Standard buttons/cards (use components)
- ❌ Typography styles (use theme classes)

---

## 🔍 Testing Checklist

After migrating each page:

- [ ] Background gradient appears correctly
- [ ] Vignette and noise overlays work
- [ ] Text is readable (proper contrast)
- [ ] Buttons have hover effects
- [ ] Cards have proper borders and glow
- [ ] Animations trigger on page load
- [ ] Responsive design works on mobile
- [ ] Focus states work for keyboard navigation
- [ ] No JavaScript errors
- [ ] Page-specific features still function

---

## 💡 Tips

1. **Incremental Migration**: Update one page at a time
2. **Keep a Backup**: Already created `style.css.backup`
3. **Test Frequently**: Check after each change
4. **Use Browser DevTools**: Inspect which CSS variables are applied
5. **Reference components_demo.html**: See all components in action
6. **Check DESIGN_SYSTEM.md**: Complete component documentation

---

## 📦 Complete Example: Migrated Button

### Before (custom inline styles):
```html
<a href="/play" style="
    display: inline-block;
    padding: 14px 32px;
    background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
    color: white;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 700;
    text-transform: uppercase;
    transition: all 0.2s;
">
    Start Game
</a>
```

### After (theme classes):
```html
<a href="/play" class="btn btn-primary">
    Start Game
</a>
```

That's **48 lines reduced to 3 lines** with the same visual result! 🎉

---

## 🎯 Priority Order

Migrate in this order for best results:

1. ✅ **index.html** (already done)
2. **home.html** (main landing page)
3. **song_selection.html** (user entry point)
4. **dashboard.html** (partial alignment already)
5. **calibrate.html, freestyle.html, game.html** (as needed)

---

## 🆘 Troubleshooting

### Issue: Background doesn't show
**Fix**: Ensure content has `position: relative; z-index: 1;`

### Issue: Buttons look wrong
**Fix**: Check that Inter font is loaded:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
```

### Issue: Colors look different
**Fix**: CSS variables only work in browsers that support them. Check compatibility or add fallbacks.

### Issue: Animations not working
**Fix**: Check `prefers-reduced-motion` setting or add `.animate-*` classes

---

## 📚 Resources

- **DESIGN_SYSTEM.md** - Complete component documentation
- **components_demo.html** - Visual component reference
- **style.css** - Source of all CSS variables
- **results.html** - Original design source

---

## ✨ Benefits After Migration

- ✅ Consistent visual style across all pages
- ✅ Easier maintenance (change once, apply everywhere)
- ✅ Smaller page sizes (less embedded CSS)
- ✅ Better accessibility (standardized focus states)
- ✅ Faster development (reusable components)
- ✅ Responsive by default
