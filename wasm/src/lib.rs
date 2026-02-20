use std::collections::HashMap;
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

/// Scan byte triplets and return packed [x, y, z, brightness, ...] as f32.
/// Keeps at most `max_points` triplets (highest frequency first).
#[wasm_bindgen]
pub fn triplet_data(data: &[u8], scale: u8, max_points: u32) -> Vec<f32> {
    if data.len() < 3 {
        return vec![];
    }

    let mut counts: HashMap<[u8; 3], u32> = HashMap::new();
    for w in data.windows(3) {
        let key = [w[0], w[1], w[2]];
        *counts.entry(key).or_insert(0) += 1;
    }

    let peak = counts.values().copied().max().unwrap_or(0);

    let mut entries: Vec<_> = counts.into_iter().collect();
    entries.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    if max_points > 0 && entries.len() > max_points as usize {
        entries.truncate(max_points as usize);
    }

    let mut result = Vec::with_capacity(entries.len() * 4);
    for (key, count) in entries {
        let b = brightness(count, peak, scale) as f32 / 255.0;
        result.push(key[0] as f32);
        result.push(key[1] as f32);
        result.push(key[2] as f32);
        result.push(b);
    }
    result
}

/// Return stats for triplet mode: [file_size, unique_triplets, max_count].
#[wasm_bindgen]
pub fn triplet_stats(data: &[u8]) -> Vec<u32> {
    if data.len() < 3 {
        return vec![data.len() as u32, 0, 0];
    }

    let mut counts: HashMap<[u8; 3], u32> = HashMap::new();
    for w in data.windows(3) {
        let key = [w[0], w[1], w[2]];
        *counts.entry(key).or_insert(0) += 1;
    }

    let peak = counts.values().copied().max().unwrap_or(0);
    let unique = counts.len() as u32;
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
    fn single_byte_input() {
        let pixels = visualize(&[0x42], 0);
        assert_eq!(pixels.len(), 256 * 256 * 4);
        // All alpha should be 255, all RGB should be 0 even for single-byte input
        for i in 0..256 * 256 {
            assert_eq!(pixels[i * 4], 0);       // R
            assert_eq!(pixels[i * 4 + 1], 0);   // G
            assert_eq!(pixels[i * 4 + 2], 0);   // B
            assert_eq!(pixels[i * 4 + 3], 255); // A
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
    fn multiple_pairs_gradient() {
        // Byte sequence: [0, 1, 0, 1, 0, 2]
        // Pairs (windows of 2): (0,1), (1,0), (0,1), (1,0), (0,2)
        // So counts are: (0,1) x2, (1,0) x2, (0,2) x1; max count is 2.
        let data = [0u8, 1, 0, 1, 0, 2];
        // Use linear brightness mode (2) so scaling is predictable.
        let pixels = visualize(&data, 2);

        // (x, y) = (0, 1) should have the maximum brightness (count 2).
        let idx_max = (1 * 256 + 0) * 4;
        let max_brightness = pixels[idx_max];
        assert_eq!(max_brightness, 255);

        // (x, y) = (0, 2) has lower frequency (count 1), so lower brightness.
        let idx_lower = (2 * 256 + 0) * 4;
        let lower_brightness = pixels[idx_lower];

        assert!(lower_brightness > 0);
        assert!(lower_brightness < max_brightness);
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
    fn brightness_sqrt() {
        assert_eq!(brightness(0, 100, 1), 0);
        assert_eq!(brightness(25, 100, 1), 128); // sqrt(25/100) = 0.5 -> ~128
        assert_eq!(brightness(100, 100, 1), 255);
    }

    #[test]
    fn file_stats_works() {
        let stats = file_stats(&[0, 1, 0, 1, 0]);
        // pairs: (0,1) x2, (1,0) x2 -> 2 unique, max 2
        assert_eq!(stats[0], 5); // file size
        assert_eq!(stats[1], 2); // unique pairs
        assert_eq!(stats[2], 2); // max count
    }

    #[test]
    fn triplet_data_empty() {
        assert!(triplet_data(&[], 0, 0).is_empty());
        assert!(triplet_data(&[1, 2], 0, 0).is_empty());
    }

    #[test]
    fn triplet_data_single() {
        let result = triplet_data(&[0x10, 0x20, 0x30], 0, 0);
        assert_eq!(result.len(), 4); // one triplet: x, y, z, brightness
        assert_eq!(result[0], 0x10 as f32);
        assert_eq!(result[1], 0x20 as f32);
        assert_eq!(result[2], 0x30 as f32);
        assert_eq!(result[3], 1.0); // single entry = max = full brightness
    }

    #[test]
    fn triplet_data_max_points() {
        // 5 bytes -> 3 triplets: (0,1,2), (1,2,3), (2,3,4)
        let result = triplet_data(&[0, 1, 2, 3, 4], 0, 2);
        // max_points=2 should limit to 2 triplets -> 8 floats
        assert_eq!(result.len(), 8);
    }

    #[test]
    fn triplet_stats_works() {
        let stats = triplet_stats(&[0, 1, 2, 0, 1, 2]);
        // triplets: (0,1,2) x2, (1,2,0) x1, (2,0,1) x1 -> 3 unique, max 2
        assert_eq!(stats[0], 6); // file size
        assert_eq!(stats[1], 3); // unique triplets
        assert_eq!(stats[2], 2); // max count
    }
}
