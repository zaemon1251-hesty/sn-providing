#!/bin/bash
# related to spotting json file
# v3 のアノテーションがある、プレミアリーグ映像を選択した

INPUT_JSON_DIR="data/spotting"
SPOTTING_MODEL="commentary_gold"

TARGET_GAME="europe_uefa-champions-league/2014-2015/2015-05-05 - 21-45 Juventus 2 - 1 Real Madrid"

INPUT_FILE="$INPUT_JSON_DIR/$SPOTTING_MODEL/$TARGET_GAME/results_spotting.json"

video_data_csv="data/from_video/players_in_frames.csv"

# related to comment csv file
INPUT_CSV_DIR="data/commentary"
COMMENT_CSV_FILE="$INPUT_CSV_DIR/scbi-v2.csv"

# related to output file
OUTPUT_FILE="outputs/$TARGET_GAME/2024-11-22-14-48-results_spotting_query.jsonl"
mkdir -p "outputs/$TARGET_GAME"


uv run python src/sn_providing/construct_query.py \
    --game "$TARGET_GAME" \
    --input_file "$INPUT_FILE" \
    --output_file "$OUTPUT_FILE" \
    --comment_csv "$COMMENT_CSV_FILE" \
    --video_data_csv "$video_data_csv"
