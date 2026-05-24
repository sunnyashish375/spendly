// Derives a stable hue (0–359) from any string so every category
// gets a consistent colour without a hardcoded mapping.
function categoryHue(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) {
        h = (h * 31 + name.charCodeAt(i)) & 0xffff;
    }
    return h % 360;
}

document.addEventListener('DOMContentLoaded', function () {
    // Colour bar fills + their track backgrounds
    document.querySelectorAll('.profile-cat-fill[data-category]').forEach(function (fill) {
        const hue = categoryHue(fill.dataset.category);
        fill.style.background = 'hsl(' + hue + ', 58%, 38%)';
        fill.parentElement.style.background = 'hsl(' + hue + ', 58%, 92%)';
    });

    // Colour category badges (profile table + expenses page)
    document.querySelectorAll('.profile-badge[data-category], .expenses-badge[data-category]').forEach(function (badge) {
        const hue = categoryHue(badge.dataset.category);
        badge.style.background = 'hsl(' + hue + ', 60%, 92%)';
        badge.style.color = 'hsl(' + hue + ', 50%, 28%)';
    });
});
