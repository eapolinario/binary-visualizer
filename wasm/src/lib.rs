use wasm_bindgen::prelude::*;

/// Scan byte pairs in the input data and return a 256x256 frequency grid
/// as a flat array of u32 counts (row-major: grid[y * 256 + x]).
fn scan_pairs(data: &[u8]) -> Vec<u32> {
    let mut grid = vec![0u32; 256 * 256];
    if data.len() < 2 {
        return grid;
    }
    for pair in data.windows(2) {
        let x = pair[0] as usize;
        let y = pair[1] as usize;
        grid[y * 256 + x] = grid[y * 256 + x].saturating_add(1);
    }
    grid
}

/// Convert a count to a grayscale 0–255 value using the requested curve.
/// Mirrors the Python `brightness()` function.
fn brightness(value: u32, max_value: u32, scale: u8) -> u8 {
    if value == 0 || max_value == 0 {
        return 0;
    }
    let ratio = match scale {
        // log
        0 => ((value as f64).ln_1p()) / ((max_value as f64).ln_1p()),
        // sqrt
        1 => (value as f64 / max_value as f64).sqrt(),
        // linear
        _ => value as f64 / max_value as f64,
    };
    let ratio = ratio.clamp(0.0, 1.0);
    let scaled = ratio * 255.0;
    // Ensure the faintest non-zero pair is not pure black (min 1).
    (scaled.round() as u8).max(1).min(255)
}

/// Accepts raw file bytes and a scale mode (0=log, 1=sqrt, 2=linear).
/// Returns RGBA pixel data (256 * 256 * 4 bytes) ready for an ImageData.
#[wasm_bindgen]
pub fn visualize(data: &[u8], scale: u8) -> Vec<u8> {
    let grid = scan_pairs(data);
    let peak = grid.iter().copied().max().unwrap_or(0);

    let mut pixels = vec![0u8; 256 * 256 * 4];
    for i in 0..256 * 256 {
        let v = brightness(grid[i], peak, scale);
        let base = i * 4;
        pixels[base] = v;     // R
        pixels[base + 1] = v; // G
        pixels[base + 2] = v; // B
        pixels[base + 3] = 255; // A
    }
    pixels
}

/// Return basic stats about the file: [file_size, unique_pairs, max_count].
#[wasm_bindgen]
pub fn file_stats(data: &[u8]) -> Vec<u32> {
    let grid = scan_pairs(data);
    let peak = grid.iter().copied().max().unwrap_or(0);
    let unique = grid.iter().filter(|&&c| c > 0).count() as u32;
    vec![data.len() as u32, unique, peak]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_input() {
        let pixels = visualize(&[], 0);
        assert_eq!(pixels.len(), 256 * 256 * 4);
        // All alpha should be 255, all RGB should be 0
        for i in 0..256 * 256 {
            assert_eq!(pixels[i * 4], 0);
            assert_eq!(pixels[i * 4 + 3], 255);
        }
    }

    #[test]
    fn single_pair() {
        // Two bytes: 0x41, 0x42 -> one pair at (0x41, 0x42)
        let pixels = visualize(&[0x41, 0x42], 0);
        // The pixel at (0x41, 0x42) should be bright (255 since it's the only/max)
        let idx = (0x42 * 256 + 0x41) * 4;
        assert_eq!(pixels[idx], 255);
    }

    #[test]
    fn brightness_log() {
        assert_eq!(brightness(0, 100, 0), 0);
        assert_eq!(brightness(100, 100, 0), 255);
    }

    #[test]
    fn brightness_linear() {
        assert_eq!(brightness(0, 100, 2), 0);
        assert_eq!(brightness(100, 100, 2), 255);
        assert_eq!(brightness(50, 100, 2), 128);
    }

    #[test]
    fn file_stats_works() {
        let stats = file_stats(&[0, 1, 0, 1, 0]);
        // pairs: (0,1) x2, (1,0) x2 -> 2 unique, max 2
        assert_eq!(stats[0], 5); // file size
        assert_eq!(stats[1], 2); // unique pairs
        assert_eq!(stats[2], 2); // max count
    }
}
