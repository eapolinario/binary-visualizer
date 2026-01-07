# Triplet Reading Performance Analysis

## Executive Summary

**Conclusion: Chunk-based file reading provides minimal to no performance improvement.**

The bottleneck in triplet scanning is **NOT file I/O**, but rather Python loop overhead and dictionary operations.

## Evidence

### 1. Profiling Results (10 MB file)

```
Method: mmap indexed
- Total time: 8.089 seconds
- Time in mmap operations: <0.001 seconds
- Time in main loop: 8.088 seconds (99.99%)

Method: chunked
- Total time: 7.497 seconds
- Time in read() calls: 0.004 seconds (0.05%)
- Time in main loop: 7.492 seconds (99.95%)
```

**File I/O accounts for less than 0.1% of total execution time.**

### 2. Benchmark Results

#### Small to Medium Files
| File Size | mmap indexed | chunked | Winner | Speedup |
|-----------|--------------|---------|--------|---------|
| 10 KB     | 0.0026s      | 0.0024s | chunked | 1.09x   |
| 100 KB    | 0.0209s      | 0.0198s | chunked | 1.05x   |
| 1 MB      | 0.2006s      | 0.1904s | chunked | 1.05x   |
| 10 MB     | 2.13s        | 2.01s   | chunked | 1.06x   |

#### Large Files (Random Data)
| File Size | mmap indexed | chunked | Winner | Speedup |
|-----------|--------------|---------|--------|---------|
| 50 MB     | 43.59s       | 50.45s  | **mmap** | 0.86x (chunked slower!) |
| 100 MB    | 105.49s      | 103.52s | chunked | 1.02x |

### 3. Key Observations

1. **Marginal gains**: Chunked reading provides at most 5-6% speedup
2. **Inconsistent**: Can actually be slower (15.7% slower for 50MB file with random data)
3. **Not I/O bound**: File reading takes <0.1% of total time
4. **Loop-bound**: 99.9% of time is spent in the Python loop doing:
   - Tuple creation
   - Dictionary lookups
   - Counter incrementing

### 4. Why Chunk-Based Reading Doesn't Help Much

The current mmap implementation:
```python
for i in range(len(mm) - 2):
    counts[(mm[i], mm[i + 1], mm[i + 2])] += 1
```

Each iteration does:
1. **Indexing** `mm[i]` - memory-mapped, extremely fast (nanoseconds)
2. **Tuple creation** `(mm[i], mm[i+1], mm[i+2])` - Python object allocation (microseconds)
3. **Dictionary operation** `counts[...]` - hash lookup (microseconds)
4. **Counter increment** `+= 1` - Python arithmetic (microseconds)

The memory-mapped indexing (step 1) is negligible compared to steps 2-4.

Chunk-based reading trades:
- **Benefit**: Slightly fewer syscalls (already negligible)
- **Cost**: Additional complexity, boundary handling, variable performance

### 5. Real Bottleneck

The bottleneck is the **10 million Python iterations** (for a 10MB file), each doing:
- Tuple allocation
- Hash computation
- Dictionary lookup
- Integer increment

These Python operations are 1000x slower than the memory-mapped file access.

## Potential Real Optimizations

If speed is critical, consider:

1. **Sampling**: Only scan every Nth triplet (loses accuracy)
2. **Cython/NumPy**: Rewrite the hot loop in Cython or use NumPy operations
3. **Pre-filtering**: Skip certain byte ranges if known to be uninteresting
4. **Parallel processing**: Split file into chunks and process in parallel
5. **Rust/C extension**: Rewrite the scanner in a compiled language

## Recommendation

**Keep the current mmap-indexed approach.** It is:
- Simple and readable
- Already quite efficient
- Not I/O bottlenecked

Chunk-based reading adds complexity for minimal and inconsistent gains.

To significantly improve performance, the entire scanning loop needs to be moved out of Python into a compiled language.
