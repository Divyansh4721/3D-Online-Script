# lsf gdrive:/3DMovies --include "*.mp4" --format "pi" --files-only > 3d_video_ids.txt


import json

with open("initData.json", "r") as f:
    data = json.load(f)

with open("ids.txt", "r") as f:
    ids = [f.strip() for f in f.readlines()]


video_ids = []
for id in ids:
    name, video_id = id.split(";")
    video_ids.append({"name": name, "id": video_id})

for i in range(len(data)):
    name = data[i]["metadata"]["name"].split(".mp4")[0]
    for video in video_ids:
        if name == video["name"].split(".mp4")[0]:
            data[i]["gdrive_id"] = video["id"]
            break

with open("finalData.json", "w") as f:
    json.dump(data, f, indent=4)