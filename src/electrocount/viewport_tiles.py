"""Stable physical-pixel grid; zoom/pan never changes already rendered tile keys."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ViewTile:
    scale: float
    column: int
    row: int
    rect: tuple
    visible: bool

    @property
    def key(self):
        return (self.scale, self.column, self.row)


def viewport_tiles(width, height, viewport, zoom, dpr=1.0, tile_pixels=512):
    """Render at least one source pixel per physical display pixel, plus a rim.

    Quarter-octave buckets keep nearby zoom levels reusable. Grid coordinates
    are integral pixels, so adjacent tiles share PDFium's pixel origin.
    """
    scale = 2 ** (math.ceil(math.log2(max(0.03125, zoom * dpr)) * 4) / 4)
    step = tile_pixels / scale
    x, y, w, h = viewport
    left, top = max(0, x), max(0, y)
    right, bottom = min(width, x + w), min(height, y + h)
    if right <= left or bottom <= top:
        return []
    first_x, first_y = int(left // step), int(top // step)
    last_x = min(math.ceil(width / step) - 1, math.ceil(right / step) - 1)
    last_y = min(math.ceil(height / step) - 1, math.ceil(bottom / step) - 1)
    center_x, center_y = (left + right) / (2 * step), (top + bottom) / (2 * step)
    tiles = []
    for row in range(max(0, first_y - 1), min(math.ceil(height / step), last_y + 2)):
        for column in range(max(0, first_x - 1), min(math.ceil(width / step), last_x + 2)):
            tx, ty = column * step, row * step
            # One pixel of overlap prevents hairline seams during fractional zoom.
            rect = (tx, ty, min(step + 1 / scale, width - tx),
                    min(step + 1 / scale, height - ty))
            visible = first_x <= column <= last_x and first_y <= row <= last_y
            tiles.append(ViewTile(scale, column, row, rect, visible))
    tiles.sort(key=lambda t: (not t.visible,
                             (t.column + .5 - center_x) ** 2 + (t.row + .5 - center_y) ** 2))
    return tiles
