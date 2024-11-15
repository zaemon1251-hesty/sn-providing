from pathlib import Path
from typing import Optional, List
from tap import Tap
import json
import pandas as pd
from dataclasses import dataclass
from loguru import logger
from datetime import datetime

logger.add("logs/{}.log".format(datetime.now().strftime("%Y-%m-%d-%H-%M-%S")))
logger.level("DEBUG")

class Arguments(Tap):
    game: str
    input_file: str
    output_file: str
    comment_csv: str
    video_data_csv: str


@dataclass
class SpottingData:
    half: int
    game_time: int
    confidence: float
    position: int
    category: str # 0(映像の説明) or 1(付加的情報)
    query: Optional[str] = None
    addiofo: Optional[List[str]] = None


@dataclass
class SpottingDataList:
    """スポッティングデータの配列"""
    spottings: List[SpottingData]
    
    @staticmethod
    def read_json(json_file: str) -> "SpottingDataList":
        data = json.load(open(json_file))

        spottings = []
        for d in data["predictions"]:
            minutes, seconds = map(int, d["gameTime"].split(" ")[-1].split(":"))
            spotting = SpottingData(
                half=int(d["half"]),
                game_time=minutes * 60 + seconds,
                confidence=float(d["confidence"]),
                position=int(d["position"]),
                category=str(d["category"])
            )
            spottings.append(spotting)

        return SpottingDataList(spottings)
    
    @staticmethod
    def filter_by_category_1(spottings: "SpottingDataList") -> "SpottingDataList":
        return SpottingDataList([s for s in spottings.spottings if s.category == "1"])

    @staticmethod
    def from_jsonline(input_file: str):
        spottings = []
        with open(input_file, 'r') as f:
            for line in f:
                spottings.append(SpottingData(**json.loads(line)))
        return SpottingDataList(spottings)

    def to_json(self, output_file: str):
        json.dump([s.__dict__ for s in self.spottings], open(output_file, "w"), ensure_ascii=False)    
    
    def to_jsonline(self, output_file: str):
        with open(output_file, 'w') as f:
            for s in self.spottings:
                f.write(json.dumps(s.__dict__, ensure_ascii=False) + "\n")
    
    def show_times(self, head: Optional[int] = None):
        head = head if head else len(self.spottings)
        for s in self.spottings[:head]:
            logger.info(f"{s.half=}, {s.game_time=}")


@dataclass
class CommentData:
    half: int
    start_time: int
    text: str
    category: str


@dataclass
class CommentDataList:
    comments: List[CommentData]
    
    @staticmethod
    def read_csv(comment_csv: str, game: str) -> "CommentDataList":
        comment_df = pd.read_csv(comment_csv)
        assert set(comment_df.columns) >= {"game", "half", "start", "end", "text", "付加的情報か"}
        
        # TODO 前処理はmethod分割したい
        
        def convert_time(time: str) -> int:
            minute, second = map(int, time.split(":"))
            return minute * 60 + second
        
        # 指定のgame に対応するコメントのみ取得
        comment_df = comment_df[comment_df["game"] == game]

        # start time を秒に変換
        if comment_df["start"].dtype == "O":
            comment_df["start"] = comment_df["start"].apply(convert_time)
        
        # 並び替え
        comment_df = comment_df.sort_values("start")
        comments = []
        for i, row in comment_df.iterrows():
            comment = CommentData(int(row["half"]), int(row["start"]), row["text"], str(row["付加的情報か"]))
            comments.append(comment)
        
        return CommentDataList(comments)

    @staticmethod
    def filter_by_half_and_time(
        comments: "CommentDataList", 
        half: int, 
        game_time: str, 
        seconds_before: int = 60
    ) -> "CommentDataList":
        """
        seconds_before 秒前から game_time までのコメントを取得
        """
        filterd_comments = [
            c for c in comments.comments
            if c.half == half and \
                c.start_time >= game_time - seconds_before and \
                c.start_time < game_time
            ]
        return CommentDataList(filterd_comments)
    
    def show_times(self, head: Optional[int] = None):
        head = head if head else len(self.comments)
        for s in self.comments[:head]:
            logger.info(f"{s.half=}, {s.start_time=}")


class VideoData:
    def __init__(self, player_csv: Path, sec_threshold: int = 2):
        # パラメータを設定
        self.sec_threshold = sec_threshold
        
        # データを読み込み
        self.player_df = pd.read_csv(player_csv)
        assert set(self.player_df.columns) >= {"game", "half", "time", "team", "name"}

    def get_data(self, game,  half: int, game_time: int) -> dict[str, str]:
        # 2秒前から2秒後の間に映っている選手名/teamを取得
        spot_players_df = self.player_df[
            (self.player_df["half"] == half) & \
            (self.player_df["game"] == game) & \
            (self.player_df["time"] >= game_time - self.sec_threshold) & \
            (self.player_df["time"] <= game_time + self.sec_threshold)
        ]
        player_team_names = spot_players_df[['team', 'name']].to_dict(orient='records')
        
        return player_team_names


def build_query(
    comments: CommentDataList, 
    max_length: int = 256, 
    *args, **kargs
) -> str:
    """
    検索クエリの内容:
    - 直近のコメント
    - TODO SoccerNet Caption Labels-caption.json のメタデータ(選手情報など)
    - TODO Game State Reconstruction の情報
    - TODO OSL Spotiing のAction Spotting の情報
    """
    query = []
    total_length = 0
    
    # commentsは時系列順に並んでいるので、逆順にして直近のコメントから取得
    for comment in reversed(comments.comments):
        if total_length + len(comment.text) > max_length:
            break
        query.append(comment.text)
        total_length += len(comment.text) + 1
    
    # 逆順にしていたので、再度逆順にして返す
    query = " ".join(reversed(query))
    query = "Previous comments: " + query
    
    # 映像中に映っている選手の名前を取得
    if "video_data" in kargs and kargs["video_data"]:
        team_game_str = " ".join([f"{p['name']} @ {p['team']}" for p in kargs['video_data']])
        query = f"Players shown in this frame: {team_game_str}\n\n" + query
    
    return query


def run(args: Arguments):
    # input_file includes json: {"UrlLocal": "path", "predictions", [{"gameTime": "1 - 00:24", "category": 0 or 1}, {...}, ...]}
    """
    1. Read files
    2. for each timestamp with label "1", 
        a. get previous comments corresponding to the timestamp 
        b. get player names and from sn-gamestate
        c. (optional) get actions from yahoo-research
    3. construct query
    """
    logger.info("Start constructing query")
    logger.info(f"{args=}")
    
    spotting_data_list = SpottingDataList.read_json(args.input_file)    
    spotting_data_list = SpottingDataList.filter_by_category_1(spotting_data_list)
    
    video_data = VideoData(args.video_data_csv)
    
    comment_data_list = CommentDataList.read_csv(args.comment_csv, args.game)
    
    logger.info("Spotting data")
    logger.info(f"{len(spotting_data_list.spottings)=}")
    logger.info("Comment data")
    logger.info(f"{len(comment_data_list.comments)=}")
    
    result_spottings = []
    
    # spotting データのtimeリスト と video_data の timeリスト を比較する
    spot_time_set = set()
    for spotting_data in spotting_data_list.spottings:
        spot_time_set.add((spotting_data.half, spotting_data.game_time))
    
    frame_time_set = set()
    for i, data in video_data.player_df.iterrows():
        frame_time_set.add((data["half"], data["time"]))
    
    # logger.info(f"{spot_time_set=}")
    # logger.info(f"{frame_time_set=}")
    # logger.info(f"{(spot_time_set & frame_time_set)=}")
    
    for spotting_data in spotting_data_list.spottings:
        filtered_comment_list = CommentDataList.filter_by_half_and_time(
            comment_data_list, 
            spotting_data.half, 
            spotting_data.game_time
        )
        player_and_teams = video_data.get_data(args.game, spotting_data.half, spotting_data.game_time)
        query = build_query(comments=filtered_comment_list, video_data=player_and_teams)
        spotting_data.query = query
        result_spottings.append(spotting_data)

    result_spottings = SpottingDataList(result_spottings)

    if args.output_file.endswith(".json"):
        result_spottings.to_json(args.output_file)
    elif args.output_file.endswith(".jsonl"):
        result_spottings.to_jsonline(args.output_file)
    
    logger.info(f"Output file is saved at {args.output_file}")

if __name__ == "__main__":
    ### construct query from the input file
    args = Arguments().parse_args()
    run(args)
