-- V6: post_url NULL 복원 — post_id_at_source + site_name으로 역산.
--
-- 배경: post_url은 V5에서 NULLABLE로 완화됐고, CrawlEvent.post_url 필드는
-- commit 69e7a7f 이후 추가됐다. 그 이전에 저장된 posts는 post_url = NULL.
-- 대시보드 "원본 게시글 열기" 버튼이 해당 데이터에서 동작하지 않는 원인.
--
-- 복원 가능 사이트 (post_id_at_source → URL 역산 규칙):
--   inven_maple           : /board/maple/2298/{id}
--   inven_lineage_classic : /board/lineageclassic/6482/{id}
--   dcard                 : /f/game/p/{id}
--   dcard_online          : /f/online/p/{id}
--   bahamut_*             : post_id = bsn{N}_snA{M} → C.php?bsn={N}&snA={M}
--   52pojie               : post_id = {A}_{B}_{C} → thread-{A}-{B}-{C}.html
--   tieba                 : /p/{id}
--
-- 복원 불가 사이트 (NULL 유지):
--   ptt / ptt_mobile_game : M.{epoch}.{letter}.{hex}.html — hex suffix 미보존

UPDATE posts p
SET post_url = CASE s.site_name
    WHEN 'inven_maple' THEN
        'https://www.inven.co.kr/board/maple/2298/' || p.post_id_at_source
    WHEN 'inven_lineage_classic' THEN
        'https://www.inven.co.kr/board/lineageclassic/6482/' || p.post_id_at_source
    WHEN 'dcard' THEN
        'https://www.dcard.tw/f/game/p/' || p.post_id_at_source
    WHEN 'dcard_online' THEN
        'https://www.dcard.tw/f/online/p/' || p.post_id_at_source
    WHEN 'tieba' THEN
        'https://tieba.baidu.com/p/' || p.post_id_at_source
    WHEN 'nga' THEN
        'https://bbs.nga.cn/read.php?tid=' || p.post_id_at_source
    WHEN '52pojie' THEN
        'https://www.52pojie.cn/thread-' || replace(p.post_id_at_source, '_', '-') || '.html'
    ELSE
        -- bahamut_* 계열: post_id = bsn{N}_snA{M}
        CASE WHEN s.site_name LIKE 'bahamut_%'
                  AND p.post_id_at_source ~ '^bsn\d+_snA\d+$' THEN
            'https://forum.gamer.com.tw/C.php?bsn=' ||
            (regexp_match(p.post_id_at_source, '^bsn(\d+)_snA\d+$'))[1] ||
            '&snA=' ||
            (regexp_match(p.post_id_at_source, '^bsn\d+_snA(\d+)$'))[1]
        ELSE NULL  -- ptt, ptt_mobile_game 등 역산 불가 → NULL 유지
        END
END
FROM sources s
WHERE p.source_id = s.id
  AND p.post_url IS NULL;
