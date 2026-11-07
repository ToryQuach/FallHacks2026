9-SLICE CHAT BUBBLE KIT  (colors: green, blue, pink, cream)
Each color folder:
  bubble_<c>_9slice.png / @2x  -> full sheet, 90x90 (1x), corners 30x30, centre 30x30
  slices/ tl t tr l c r bl b br -> the 9 pieces separately (corners fixed, t/b stretch X, l/r stretch Y, c stretch both)
  tail_left_<c> / tail_right_<c> -> separate tail, overlap its top 5px on the bubble's bottom outline
decor/ side_tab (navy/pink/red blocks), sparkles, blush -> optional overlays
Outline = 5px (1x), corner radius = 24px (1x). See demo.html for CSS border-image usage.
Android: use the sheet as a Nine-Patch; Unity/Godot/SwiftUI: slice insets = 30px (60px @2x).
