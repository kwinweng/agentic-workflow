"""测试共享样例数据。"""

from pipeline.models import Segment, Transcript, VideoRef

VIDEO = VideoRef(
    bvid="BV1GJ411x7h7", aid=100, cid=2222, part_no=2, total_parts=3,
    title="测试/课程: 高级篇", part_title="第二集", duration_sec=4000,
    up_name="某UP", url="https://www.bilibili.com/video/BV1GJ411x7h7?p=2",
)

TRANSCRIPT = Transcript(
    source="cc",
    segments=[
        Segment(start=0.0, end=2.0, text="大家好"),
        Segment(start=2.1, end=4.0, text="今天讲架构"),
        Segment(start=10.0, end=12.0, text="第二段开始"),  # 间隔>2.5s，另起段落
    ],
)
