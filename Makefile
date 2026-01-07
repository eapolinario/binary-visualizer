INPUT ?=
OUTPUT ?= output.ppm
OUTPUT_DIR ?= .
SCALE ?= log
MODE ?= 2d
BIN_DIR ?=
BIN_JOBS ?= 0
PPM_DIR ?=
PPM_VIDEO_OUTPUT ?=
PPM_FRAMERATE ?= 4

.PHONY: run run-3d test lint ppm-video bin-ppm bin-video

# Build a PPM for a single input binary.
run:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make run INPUT=/path/to/binary [OUTPUT=output.ppm SCALE=log MODE=2d]"; \
		exit 1; \
	fi
	uv run visualize.py --mode $(MODE) --scale $(SCALE) -o $(OUTPUT) $(INPUT)

# Build a 3D HTML visualization for a single input binary.
# Uses OUTPUT_DIR instead of OUTPUT, and derives filename from INPUT.
run-3d:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make run-3d INPUT=/path/to/binary [OUTPUT_DIR=. SCALE=log]"; \
		exit 1; \
	fi
	@mkdir -p $(OUTPUT_DIR)
	@input_basename=$$(basename "$(INPUT)"); \
	output_file="$(OUTPUT_DIR)/$${input_basename}.html"; \
	uv run visualize.py --mode 3d --scale $(SCALE) -o "$$output_file" $(INPUT)

test:
	PYTHONPATH=. uv run --with pytest --with plotly --with tqdm pytest tests/test_visualize.py

lint:
	uv run ruff check

# Convert a directory of PPMs to an MP4 using ffmpeg.
ppm-video:
	@if [ -z "$(PPM_DIR)" ]; then \
		echo "PPM_DIR is required. Pass PPM_DIR=/path/to/dir"; \
		exit 1; \
	fi
	@if [ -z "$(PPM_VIDEO_OUTPUT)" ]; then \
		echo "PPM_VIDEO_OUTPUT is required and should be a full path to the mp4 output"; \
		exit 1; \
	fi
	@if [ -z "$$(find $(PPM_DIR) -maxdepth 1 -name '*.ppm' -print -quit)" ]; then \
		echo "No .ppm files found in $(PPM_DIR)"; \
		exit 1; \
	fi
	@tmp_ssa=$$(mktemp --suffix=.ssa); \
	uv run python scripts/ppm_labels.py --ppm-dir "$(PPM_DIR)" --framerate $(PPM_FRAMERATE) --output "$$tmp_ssa"; \
	ffmpeg -y -framerate $(PPM_FRAMERATE) -pattern_type glob -i '$(PPM_DIR)/*.ppm' -vf "pad=iw:ih+60:0:0:black,subtitles='$$tmp_ssa'" -c:v libx264 -preset veryslow -crf 0 -pix_fmt yuv444p $(PPM_VIDEO_OUTPUT); \
	rm -f "$$tmp_ssa"

# For every binary in BIN_DIR, generate a PPM in PPM_DIR.
bin-ppm:
	@if [ -z "$(BIN_DIR)" ]; then \
		echo "Usage: make bin-ppm BIN_DIR=/path/to/bin_dir PPM_DIR=/path/to/ppm_dir [SCALE=log BIN_JOBS=0]"; \
		exit 1; \
	fi
	@if [ ! -d "$(BIN_DIR)" ]; then \
		echo "BIN_DIR '$(BIN_DIR)' does not exist"; \
		exit 1; \
	fi
	@if [ -z "$$(find $(BIN_DIR) -maxdepth 1 -type f -print -quit)" ]; then \
		echo "No files found in $(BIN_DIR)"; \
		exit 1; \
	fi
	@if [ -z "$(PPM_DIR)" ]; then \
		echo "PPM_DIR is required for bin-ppm"; \
		exit 1; \
	fi
	mkdir -p $(PPM_DIR)
	find -L $(BIN_DIR) -readable -maxdepth 1 -type f -print0 | \
		xargs -0 -P $(BIN_JOBS) -I{} sh -c 'name=$$(basename "$$1"); echo "Generating PPM for $$1"; $(MAKE) --no-print-directory run INPUT="$$1" OUTPUT="$(PPM_DIR)/$$name.ppm" SCALE=$(SCALE) MODE=$(MODE)' sh {}

# For every binary in BIN_DIR, generate a PPM and assemble them into a video.
bin-video:
	$(MAKE) --no-print-directory bin-ppm BIN_DIR=$(BIN_DIR) PPM_DIR=$(PPM_DIR) SCALE=$(SCALE) BIN_JOBS=$(BIN_JOBS)
	$(MAKE) --no-print-directory ppm-video PPM_DIR=$(PPM_DIR) PPM_VIDEO_OUTPUT=$(if $(PPM_VIDEO_OUTPUT),$(PPM_VIDEO_OUTPUT),$(abspath $(PPM_DIR))/output.mp4)
