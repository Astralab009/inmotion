import os
import psycopg2

url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

# 1. 获取 chain_id
cur.execute("SELECT id FROM chains WHERE name = '银行'")
row = cur.fetchone()
if not row:
    print("错误：chains 表中没有银行记录，请先在 Supabase SQL Editor 中插入。")
    cur.close()
    conn.close()
    exit(1)
chain_id = row[0]

# 2. 插入环节，并记录 segment_name -> id
segments_data = [
    ('upstream', '存款吸收与同业拆借'),
    ('upstream', '资本补充'),
    ('midstream', '对公信贷'),
    ('midstream', '零售信贷'),
    ('midstream', '中间业务'),
    ('midstream', '风险管理'),
    ('downstream', '物理网点'),
    ('downstream', '数字银行'),
    ('downstream', '银企对接')
]
seg_ids = {}
for pos, name in segments_data:
    cur.execute(
        "INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id",
        (chain_id, pos, name)
    )
    seg_id = cur.fetchone()[0]
    seg_ids[name] = seg_id
    print(f"插入环节: {name} -> {seg_id}")

# 3. 插入板块，并记录 (sector_name) -> id
sectors_data = [
    ('存款业务', '存款吸收与同业拆借'),
    ('同业存单', '存款吸收与同业拆借'),
    ('优先股/永续债', '资本补充'),
    ('对公贷款', '对公信贷'),
    ('零售贷款', '零售信贷'),
    ('住房按揭', '零售信贷'),
    ('财富管理', '中间业务'),
    ('支付结算', '中间业务'),
    ('不良资产处置', '风险管理'),
    ('零售银行', '物理网点'),
    ('金融科技/数字银行', '数字银行'),
    ('企业银行服务', '银企对接')
]
sector_ids = {}
for sname, segname in sectors_data:
    seg_id = seg_ids[segname]
    cur.execute(
        "INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id",
        (sname, seg_id)
    )
    sec_id = cur.fetchone()[0]
    sector_ids[sname] = sec_id
    print(f"插入板块: {sname} -> {sec_id}")

# 4. 插入股票，使用 sector_ids
stocks_data = [
    ('601398', '工商银行', '存款业务', '核心龙头'),
    ('601939', '建设银行', '存款业务', '核心龙头'),
    ('601166', '兴业银行', '同业存单', '核心龙头'),
    ('600000', '浦发银行', '同业存单', '一般关联'),
    ('601398', '工商银行', '优先股/永续债', '核心龙头'),
    ('601288', '农业银行', '优先股/永续债', '核心龙头'),
    ('601398', '工商银行', '对公贷款', '核心龙头'),
    ('601939', '建设银行', '对公贷款', '核心龙头'),
    ('600036', '招商银行', '零售贷款', '核心龙头'),
    ('000001', '平安银行', '零售贷款', '核心龙头'),
    ('601939', '建设银行', '住房按揭', '核心龙头'),
    ('601288', '农业银行', '住房按揭', '核心龙头'),
    ('600036', '招商银行', '财富管理', '核心龙头'),
    ('601166', '兴业银行', '财富管理', '一般关联'),
    ('601398', '工商银行', '支付结算', '核心龙头'),
    ('601939', '建设银行', '支付结算', '一般关联'),
    ('01359.HK', '中国信达', '不良资产处置', '核心龙头'),
    ('000567', '海德股份', '不良资产处置', '核心龙头'),
    ('600036', '招商银行', '零售银行', '核心龙头'),
    ('601658', '邮储银行', '零售银行', '核心龙头'),
    ('000001', '平安银行', '金融科技/数字银行', '核心龙头'),
    ('600036', '招商银行', '金融科技/数字银行', '核心龙头'),
    ('601398', '工商银行', '企业银行服务', '核心龙头'),
    ('601939', '建设银行', '企业银行服务', '核心龙头')
]
for code, name, sname, relevance in stocks_data:
    sec_id = sector_ids[sname]
    cur.execute(
        "INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)",
        (code, name, sec_id, relevance)
    )
    print(f"插入股票: {name} ({code}) 到 {sname}")

print("银行产业链导入成功！")
cur.close()
conn.close()
