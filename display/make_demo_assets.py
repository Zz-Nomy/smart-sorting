"""Create tiny PPM placeholders without installing an image library."""

from pathlib import Path


OUT = Path(__file__).resolve().parent / "assets"


def make(name: str, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    pixels = " ".join(str(v) for v in (*top, *bottom, *top, *bottom))
    (OUT / name).write_text(f"P3\n2 2\n255\n{pixels}\n", encoding="ascii")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    make("red_cylinder.ppm", (255, 100, 100), (190, 30, 30))
    make("blue_cube.ppm", (90, 160, 255), (25, 75, 190))
    make("yellow_triangle.ppm", (255, 220, 70), (180, 125, 10))
    print(f"created demo assets in {OUT}")


if __name__ == "__main__":
    main()
