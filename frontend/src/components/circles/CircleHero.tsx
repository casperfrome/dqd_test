import type { FanCircleDetail } from "../../api/types";

export function CircleHero({ circle }: { circle: FanCircleDetail }) {
  return (
    <div className="circle-hero">
      <img src={circle.logo_url} alt="" />
      <div>
        <p className="eyebrow">{circle.league_name}</p>
        <h2>{circle.board_name}</h2>
        <p>{circle.description}</p>
        <div className="stats-row">
          <span>{circle.post_count} 帖子</span>
          <span>{circle.follower_count} 关注</span>
          <span>圈主：{circle.owner?.nickname ?? "待分配"}</span>
        </div>
      </div>
    </div>
  );
}
