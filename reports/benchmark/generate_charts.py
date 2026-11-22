# -*- coding: utf-8 -*-
"""
Generate professional SVG charts from empirical benchmark results.
Zero third-party dependencies required.
Outputs:
- reports/figures/chart_execution_time.svg
- reports/figures/chart_buffer_io.svg
- reports/figures/chart_sargability.svg
"""

import os

def create_bar_chart_svg(title, categories, values_before, values_after, ylabel, filename, is_log=False):
    width = 800
    height = 450
    margin_top = 60
    margin_bottom = 80
    margin_left = 90
    margin_right = 50

    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    max_val = max(max(values_before), max(values_after)) * 1.15
    if max_val == 0:
        max_val = 1.0

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="background-color: #FFFFFF; font-family: Arial, sans-serif;">')

    # Title
    svg.append(f'<text x="{width/2}" y="35" text-anchor="middle" font-size="16" font-weight="bold" fill="#1B365D">{title}</text>')

    # Legend
    leg_x = width - margin_right - 220
    leg_y = 25
    svg.append(f'<rect x="{leg_x}" y="{leg_y}" width="16" height="12" fill="#E53E3E" rx="2"/>')
    svg.append(f'<text x="{leg_x+22}" y="{leg_y+10}" font-size="11" fill="#4A5568">Tanpa Indeks (Baseline)</text>')
    svg.append(f'<rect x="{leg_x+120}" y="{leg_y}" width="16" height="12" fill="#3182CE" rx="2"/>')
    svg.append(f'<text x="{leg_x+142}" y="{leg_y+10}" font-size="11" fill="#4A5568">Dengan Indeks</text>')

    # Axes
    svg.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#CBD5E0" stroke-width="1.5"/>')
    svg.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#CBD5E0" stroke-width="1.5"/>')

    # Y-axis label
    svg.append(f'<text x="{-height/2}" y="25" text-anchor="middle" transform="rotate(-90)" font-size="12" font-weight="bold" fill="#4A5568">{ylabel}</text>')

    # Gridlines & Y-ticks
    num_ticks = 5
    for i in range(num_ticks + 1):
        tick_val = (max_val / num_ticks) * i
        y_pos = margin_top + plot_h - (i / num_ticks) * plot_h
        svg.append(f'<line x1="{margin_left}" y1="{y_pos}" x2="{margin_left + plot_w}" y2="{y_pos}" stroke="#EDF2F7" stroke-width="1"/>')
        svg.append(f'<text x="{margin_left - 10}" y="{y_pos + 4}" text-anchor="end" font-size="10" fill="#718096">{tick_val:.1f}</text>')

    # Bars
    n = len(categories)
    group_width = plot_w / n
    bar_width = group_width * 0.32

    for i in range(n):
        cx = margin_left + i * group_width + group_width / 2

        # Bar 1 (Before)
        val_b = values_before[i]
        bar_h_b = (val_b / max_val) * plot_h
        x_b = cx - bar_width - 3
        y_b = margin_top + plot_h - bar_h_b
        svg.append(f'<rect x="{x_b}" y="{y_b}" width="{bar_width}" height="{bar_h_b}" fill="#E53E3E" rx="3"/>')
        svg.append(f'<text x="{x_b + bar_width/2}" y="{y_b - 5}" text-anchor="middle" font-size="9" font-weight="bold" fill="#C53030">{val_b:.2f}</text>')

        # Bar 2 (After)
        val_a = values_after[i]
        bar_h_a = (val_a / max_val) * plot_h
        x_a = cx + 3
        y_a = margin_top + plot_h - bar_h_a
        svg.append(f'<rect x="{x_a}" y="{y_a}" width="{bar_width}" height="{bar_h_a}" fill="#3182CE" rx="3"/>')
        svg.append(f'<text x="{x_a + bar_width/2}" y="{y_a - 5}" text-anchor="middle" font-size="9" font-weight="bold" fill="#2B6CB0">{val_a:.2f}</text>')

        # Category label
        cat_name = categories[i]
        svg.append(f'<text x="{cx}" y="{margin_top + plot_h + 20}" text-anchor="middle" font-size="11" font-weight="bold" fill="#2D3748">{cat_name}</text>')

    svg.append('</svg>')

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg))
    print(f"Chart saved: {filename}")

def main():
    cats = ["1. Radar Sesi", "2. Riwayat User", "3. Omzet Bulan", "4. Antrean Seller", "5. Sargable Range"]
    time_before = [0.28, 3.71, 19.25, 8.99, 0.11]
    time_after = [0.03, 0.06, 20.73, 4.88, 0.03]

    create_bar_chart_svg(
        title="Perbandingan Waktu Eksekusi Kueri (Execution Time ms)",
        categories=cats,
        values_before=time_before,
        values_after=time_after,
        ylabel="Execution Time (milidetik)",
        filename="reports/figures/chart_execution_time.svg"
    )

    buf_before = [67, 1669, 1577, 1862, 68]
    buf_after = [3, 32, 1577, 1650, 33]

    create_bar_chart_svg(
        title="Perbandingan Pemindaian Blok Memori Buffer (Shared Hits & Reads)",
        categories=cats,
        values_before=buf_before,
        values_after=buf_after,
        ylabel="Jumlah Blok Halaman (8 KB Page)",
        filename="reports/figures/chart_buffer_io.svg"
    )

    # Sargability comparison
    sarg_cats = ["Non-Sargable (date())", "Sargable Range Query"]
    sarg_time = [6.76, 0.03]
    sarg_dummy = [0.0, 0.0]

    create_bar_chart_svg(
        title="Dampak Sargability: date(col) vs Rentang Waktu Eksplisit",
        categories=sarg_cats,
        values_before=[6.76, 0.0],
        values_after=[0.0, 0.03],
        ylabel="Execution Time (ms)",
        filename="reports/figures/chart_sargability.svg"
    )

if __name__ == "__main__":
    main()
