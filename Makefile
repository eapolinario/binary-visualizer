INPUT ?=
OUTPUT ?= output.ppm
SCALE ?= log
PPM_DIR ?=
PPM_VIDEO_OUTPUT ?=
PPM_FRAMERATE ?= 4
BIN_DIR ?=
BIN_JOBS ?= 0

.PHONY: run test lint ppm-video bin-video

# Build a PPM for a single input binary.
run:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make run INPUT=/path/to/binary [OUTPUT=output.ppm SCALE=log]"; \
		exit 1; \
	fi
	uv run visualize.py --scale $(SCALE) -o $(OUTPUT) $(INPUT)

test:
	PYTHONPATH=. uv run --with pytest pytest tests/test_visualize.py

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

# For every binary in BIN_DIR, generate a PPM and assemble them into a video.
bin-video:
	@if [ -z "$(BIN_DIR)" ]; then \
		echo "Usage: make bin-video BIN_DIR=/path/to/bin_dir PPM_DIR=/path/to/ppm_dir [PPM_VIDEO_OUTPUT=output.mp4]"; \
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
		echo "PPM_DIR is required for bin-video"; \
		exit 1; \
	fi
	mkdir -p $(PPM_DIR)
	find -L $(BIN_DIR) -readable -maxdepth 1 -type f -print0 | \
		xargs -0 -P $(BIN_JOBS) -I{} sh -c 'name=$$(basename "$$1"); echo "Generating PPM for $$1"; $(MAKE) --no-print-directory run INPUT="$$1" OUTPUT="$(PPM_DIR)/$$name.ppm" SCALE=$(SCALE)' sh {}
	$(MAKE) --no-print-directory ppm-video PPM_DIR=$(PPM_DIR) PPM_VIDEO_OUTPUT=$(if $(PPM_VIDEO_OUTPUT),$(PPM_VIDEO_OUTPUT),$(abspath $(PPM_DIR))/output.mp4)
