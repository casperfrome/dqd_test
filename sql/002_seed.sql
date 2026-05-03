INSERT OR IGNORE INTO fan_circles (
    club_name,
    board_name,
    league_name,
    logo_url,
    owner_user_id,
    description,
    created_at,
    updated_at
) VALUES
    (
        '尤文图斯',
        '尤文图斯-球迷圈',
        'Serie A',
        '/static/logos/juventus.svg',
        NULL,
        '黑白军团的赛场讨论区。',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        '拜仁慕尼黑',
        '拜仁慕尼黑-球迷圈',
        'Bundesliga',
        '/static/logos/bayern-munich.svg',
        NULL,
        '南部之星的资讯、比赛和转会讨论。',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        '曼彻斯特联',
        '曼彻斯特联-球迷圈',
        'Premier League',
        '/static/logos/manchester-united.svg',
        NULL,
        '红魔球迷交流区。',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        '切尔西',
        '切尔西-球迷圈',
        'Premier League',
        '/static/logos/chelsea.svg',
        NULL,
        '蓝军比赛、战术与阵容讨论。',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    );
