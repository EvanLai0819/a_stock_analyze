# -*- coding: utf-8 -*-
"""
===================================
板块资金流向报告生成器
===================================

职责：
1. 生成板块资金流向MD格式报告
2. 包含Top板块排名、龙头股、轮动分析、预警信息
3. 发送邮件通知

使用方式：
    reporter = IndustryMoneyflowReporter()
    
    # 生成报告
    report_path = reporter.generate_report(trade_date=date.today())
    
    # 发送邮件
    reporter.send_email_report(report_path)
"""

import logging
import os
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from src.industry_moneyflow_tracker import IndustryMoneyflowTracker
from src.notification import NotificationService

logger = logging.getLogger(__name__)


class IndustryMoneyflowReporter:
    """
    板块资金流向报告生成器
    """
    
    def __init__(self):
        """
        初始化报告生成器
        """
        self.tracker = IndustryMoneyflowTracker()
        self.notifier = NotificationService()
    
    def generate_report(
        self,
        trade_date: Optional[date] = None,
        top_limit: int = 10
    ) -> Optional[str]:
        """
        生成板块资金流向MD报告
        
        Args:
            trade_date: 交易日期（可选，默认为今天）
            top_limit: Top板块数量（默认10）
        
        Returns:
            报告文件路径，如果失败返回None
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块报告] 开始生成 {trade_date} 的板块资金流向报告...")
        
        try:
            # 1. 保存今日板块资金流向数据
            save_result = self.tracker.save_daily_moneyflow(trade_date)
            
            if not save_result['success']:
                logger.error(f"[板块报告] 保存板块数据失败: {save_result['message']}")
                return None
            
            # 2. 获取Top流入板块
            top_inflow = self.tracker.get_top_industries(trade_date, limit=top_limit, direction='inflow')
            
            # 3. 获取Top流出板块
            top_outflow = self.tracker.get_top_industries(trade_date, limit=top_limit, direction='outflow')
            
            # 4. 获取板块轮动分析
            rotations = self.tracker.analyze_industry_rotation(trade_date)
            
            # 5. 获取预警信息
            alerts = self.tracker.detect_moneyflow_alerts(min_days=1, threshold_amount=0)
            
            # 6. 构建MD报告内容
            report_content = self._build_report_content(
                trade_date=trade_date,
                top_inflow=top_inflow,
                top_outflow=top_outflow,
                rotations=rotations,
                alerts=alerts,
                top_limit=top_limit
            )
            
            # 7. 保存报告文件
            report_dir = 'reports'
            os.makedirs(report_dir, exist_ok=True)
            
            report_filename = f'industry_moneyflow_report_{trade_date.strftime("%Y%m%d")}.md'
            report_path = os.path.join(report_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"[板块报告] 报告已保存: {report_path}")
            
            return report_path
            
        except Exception as e:
            logger.error(f"[板块报告] 生成报告失败: {e}")
            return None
    
    def _build_report_content(
        self,
        trade_date: date,
        top_inflow: List[Dict[str, Any]],
        top_outflow: List[Dict[str, Any]],
        rotations: List[Dict[str, Any]],
        alerts: List[Dict[str, Any]],
        top_limit: int
    ) -> str:
        """
        构建MD报告内容
        
        Args:
            trade_date: 交易日期
            top_inflow: Top流入板块
            top_outflow: Top流出板块
            rotations: 板块轮动分析
            alerts: 预警信息
            top_limit: Top板块数量
        
        Returns:
            MD格式报告内容
        """
        # 报告标题和基本信息
        content = f"""# 板块资金流向监测报告

**数据时间**: {trade_date.strftime('%Y-%m-%d')}
**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据源**: Tushare Pro (moneyflow_ind_ths)

---

## 📊 核心发现

当日市场资金流向主要特征：

"""
        
        # 添加核心发现
        if top_inflow and top_outflow:
            top_inflow_first = top_inflow[0]
            top_outflow_first = top_outflow[0]
            
            content += f"""1. 【领涨板块】 **{top_inflow_first['industry_name']}** 板块吸金 **{abs(top_inflow_first['net_amount']):.2f}亿** 领涨，涨幅 **{top_inflow_first['pct_change']:.2f}%**，龙头股 **{top_inflow_first['lead_stock_name']}** (涨 **{top_inflow_first['lead_stock_change']:.2f}%**)。

2. 【领跌板块】 **{top_outflow_first['industry_name']}** 板块净流出 **{abs(top_outflow_first['net_amount']):.2f}亿** 居首，跌幅 **{top_outflow_first['pct_change']:.2f}%**，龙头股 **{top_outflow_first['lead_stock_name']}** (涨 **{top_outflow_first['lead_stock_change']:.2f}%**)。

3. 【资金轮动】 资金从流出板块转向流入板块，发现 **{len(rotations)}** 个轮动组合，重点关注资金流向变化。

4. 【预警信号】 检测到 **{len(alerts)}** 个板块资金流向预警，包括连续流入/流出和异常波动。

---

"""
        
        # Top流入板块表格
        content += f"""## 🔥 Top {top_limit} 资金流入板块

"""
        
        content += "| 板块名称 | 净流入金额(亿) | 板块涨跌幅(%) | 龙头股 | 龙头股涨跌(%) | 涨幅前3龙头 | 资金流入前3龙头 |\n"
        content += "|---------|-------------|------------|--------|------------|-----------|--------------|\n"
        
        for i, ind in enumerate(top_inflow, 1):
            # Get top 3 stocks by price change (涨幅龙头)
            top3_price_stocks = self.tracker.get_top3_lead_stocks_per_industry(ind['industry_name'], trade_date)
            
            # Get top 3 stocks by money inflow (资金流入龙头)
            top3_moneyflow_stocks = self.tracker.get_top3_moneyflow_stocks_per_industry(ind['industry_name'], trade_date)
            
            # Build top 3 price leaders string
            top3_price_str = ""
            if top3_price_stocks:
                top3_price_str = "<br>".join([f"{s['stock_name']}({s['stock_code']}) +{s['pct_change']:.2f}%" for s in top3_price_stocks])
            else:
                top3_price_str = f"{ind['lead_stock_name']} +{ind['lead_stock_change']:.2f}%"
            
            # Build top 3 money inflow leaders string
            top3_moneyflow_str = ""
            if top3_moneyflow_stocks:
                top3_moneyflow_str = "<br>".join([f"{s['stock_name']}({s['stock_code']}) +{s['net_mf_amount']:.2f}亿" for s in top3_moneyflow_stocks])
            else:
                top3_moneyflow_str = "暂无数据"
            
            content += f"| {ind['industry_name']} | {ind['net_amount']:.2f} | {ind['pct_change']:.2f} | {ind['lead_stock_name']} | {ind['lead_stock_change']:.2f} | {top3_price_str} | {top3_moneyflow_str} |\n"
        
        content += "\n---\n\n"
        
        # Top流出板块表格
        content += f"""## ❄️ Top {top_limit} 资金流出板块

"""
        
        content += "| 板块名称 | 净流出金额(亿) | 板块涨跌幅(%) | 龙头股 | 龙头股涨跌(%) | 涨幅前3龙头 | 资金流入前3龙头 |\n"
        content += "|---------|-------------|------------|--------|------------|-----------|--------------|\n"
        
        for i, ind in enumerate(top_outflow, 1):
            # Get top 3 stocks by price change (涨幅龙头)
            top3_price_stocks = self.tracker.get_top3_lead_stocks_per_industry(ind['industry_name'], trade_date)
            
            # Get top 3 stocks by money inflow (资金流入龙头)
            top3_moneyflow_stocks = self.tracker.get_top3_moneyflow_stocks_per_industry(ind['industry_name'], trade_date)
            
            # Build top 3 price leaders string
            top3_price_str = ""
            if top3_price_stocks:
                top3_price_str = "<br>".join([f"{s['stock_name']}({s['stock_code']}) +{s['pct_change']:.2f}%" for s in top3_price_stocks])
            else:
                top3_price_str = f"{ind['lead_stock_name']} +{ind['lead_stock_change']:.2f}%"
            
            # Build top 3 money inflow leaders string
            top3_moneyflow_str = ""
            if top3_moneyflow_stocks:
                top3_moneyflow_str = "<br>".join([f"{s['stock_name']}({s['stock_code']}) +{s['net_mf_amount']:.2f}亿" for s in top3_moneyflow_stocks])
            else:
                top3_moneyflow_str = "暂无数据"
            
            content += f"| {ind['industry_name']} | {abs(ind['net_amount']):.2f} | {ind['pct_change']:.2f} | {ind['lead_stock_name']} | {ind['lead_stock_change']:.2f} | {top3_price_str} | {top3_moneyflow_str} |\n"
        
        content += "\n---\n\n"
        
        # 板块轮动分析
        if rotations:
            content += f"""## 🔄 板块资金轮动分析

发现 **{len(rotations)}** 个资金轮动组合：

"""
            
            # 只显示前20个轮动组合
            display_rotations = rotations[:20]
            
            for i, rotation in enumerate(display_rotations, 1):
                content += f"""{i}. **{rotation['outflow_industry']} → {rotation['inflow_industry']}**
   - 流出金额: {abs(rotation['outflow_amount']):.2f}亿
   - 流入金额: {abs(rotation['inflow_amount']):.2f}亿
   - 轮动强度: **{rotation['rotation_type']}**
   - 轮动原因: {rotation['rotation_reason']}

"""
            
            if len(rotations) > 20:
                content += f"\n*（共发现 {len(rotations)} 个轮动组合，仅显示前20个）*\n\n"
        
        content += "---\n\n"
        
        # 预警信息
        if alerts:
            content += f"""## ⚠️ 板块资金流向预警

检测到 **{len(alerts)}** 个板块资金流向预警：

"""
            
            # 分类预警
            inflow_alerts = [a for a in alerts if '连续流入' in a['alert_type']]
            outflow_alerts = [a for a in alerts if '连续流出' in a['alert_type']]
            
            # 连续流入预警
            if inflow_alerts:
                content += f"""### 📈 连续流入预警 ({len(inflow_alerts)}个)

"""
                
                for i, alert in enumerate(inflow_alerts[:10], 1):  # 只显示前10个
                    content += f"""{i}. **{alert['industry_name']}**
   - 连续天数: {alert['consecutive_days']}天
   - 累计流入: {abs(alert['total_amount']):.2f}亿
   - 预警级别: {alert['alert_level']}
   - 建议: {alert['recommendation']}

"""
                
                if len(inflow_alerts) > 10:
                    content += f"\n*（共 {len(inflow_alerts)} 个流入预警，仅显示前10个）*\n\n"
            
            # 连续流出预警
            if outflow_alerts:
                content += f"""### 📉 连续流出预警 ({len(outflow_alerts)}个)

"""
                
                for i, alert in enumerate(outflow_alerts[:10], 1):  # 只显示前10个
                    content += f"""{i}. **{alert['industry_name']}**
   - 连续天数: {alert['consecutive_days']}天
   - 累计流出: {abs(alert['total_amount']):.2f}亿
   - 预警级别: {alert['alert_level']}
   - 建议: {alert['recommendation']}

"""
                
                if len(outflow_alerts) > 10:
                    content += f"\n*（共 {len(outflow_alerts)} 个流出预警，仅显示前10个）*\n\n"
        
        content += "---\n\n"
        
        # 报告结尾
        content += f"""## 💡 操作建议

1. **关注热门板块**：重点关注资金持续流入的热门板块（如元件、半导体、通信设备），把握市场热点。

2. **规避冷门板块**：谨慎对待资金持续流出的冷门板块（如IT服务、电池、电力），避免追高。

3. **跟踪龙头股**：跟踪热门板块的前3龙头股，作为该板块的代表性标的。

4. **观察轮动趋势**：密切关注资金轮动趋势，把握板块间的资金流动方向。

5. **设置预警监控**：持续监控板块资金流向预警，及时发现异常波动。

---

## 📋 数据说明

- **数据来源**: Tushare Pro (moneyflow_ind_ths接口)
- **板块分类**: 同花顺行业分类
- **资金流向**: 主力资金净流入/净流出
- **龙头股**: 板块内涨跌幅最大的股票
- **前3龙头股**: 板块内涨跌幅排名前三的股票

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return content
    
    def send_email_report(self, report_path: str) -> bool:
        """
        发送邮件报告
        
        Args:
            report_path: 报告文件路径
        
        Returns:
            发送成功返回True，失败返回False
        """
        logger.info(f"[板块报告] 开始发送邮件报告...")
        
        try:
            # 读取报告内容
            with open(report_path, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            # 提取报告日期
            report_date = datetime.now().strftime('%Y-%m-%d')
            
            # 发送邮件
            subject = f'📊 板块资金流向监测报告 - {report_date}'
            
            # 使用NotificationService的send_to_email方法
            success = self.notifier.send_to_email(
                content=report_content,
                subject=subject
            )
            
            if success:
                logger.info(f"[板块报告] 邮件报告发送成功")
                return True
            else:
                logger.error(f"[板块报告] 邮件报告发送失败")
                return False
                
        except Exception as e:
            logger.error(f"[板块报告] 发送邮件报告失败: {e}")
            return False