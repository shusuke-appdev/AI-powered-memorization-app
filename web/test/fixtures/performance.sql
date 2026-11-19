-- Synthetic data only. Apply inside an isolated test database or rolled-back transaction.
insert into public.source_cards(id,user_id,source_text,title,category,card_type,study_tags)
select md5('perf-source-'||i)::uuid, :'owner'::uuid,
  repeat('重要な事情を順に確認する。',12)||'【目的】と【要件】を記憶する。',
  '検証用の原文 '||i, '民法', '規範', array['分野 '||i%20]
from generate_series(1,545) i;

insert into public.cards(id,user_id,source_id,question,answer,title,category,card_type,rank,blank_count,
    next_review,study_layout,study_archived_at)
select md5('perf-card-'||i)::uuid, :'owner'::uuid, md5('perf-source-'||(1+(i-1)%545))::uuid,
  repeat('関連する事情を確認する。',15)||'______と______を記憶する。', '目的 / 要件',
  '検証用のカード '||i,'民法','規範',(array['A+','A','B+','B','C'])[1+i%5],2,
  study_private.today()-(i%17), jsonb_build_array(repeat('関連する事情を確認する。',15),
    jsonb_build_object('hole',1,'answer','目的'),'と',jsonb_build_object('hole',2,'answer','要件'),'を記憶する。'),
  case when i>1631 then now() end
from generate_series(1,2727) i;
