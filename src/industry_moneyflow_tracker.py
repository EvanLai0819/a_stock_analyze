# -*- coding: utf-8 -*-
"""
===================================
板块资金流向追踪系统
===================================

职责：
1. 板块资金流向历史追踪（连续多日数据存储和趋势分析）
2. 板块资金流向排名监控（Top N板块实时监控和排名变化）
3. 板块轮动分析（资金在不同板块间的流动分析）
4. 板块资金流向预警（连续流入/流出预警和异常波动检测）
5. 筛选连续流入板块龙头股

使用方式：
    tracker = IndustryMoneyflowTracker()
    
    # 保存每日板块资金流向数据
    tracker.save_daily_moneyflow()
    
    # 获取板块资金流向历史趋势
    history = tracker.get_industry_moneyflow_history('化学制药', days=10)
    
    # 获取Top N板块排名
    top_inflow = tracker.get_top_industries(limit=10, sort_by='net_amount')
    
    # 检测板块资金流向预警
    alerts = tracker.detect_moneyflow_alerts()
    
    # 筛选连续流入板块的龙头股
    lead_stocks = tracker.get_lead_stocks_in_continuous_inflow_industries(min_days=3)
"""

import logging
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from src.storage import (
    get_db,
    IndustryMoneyflowDaily,
    IndustryMoneyflowAlert,
    IndustryRotation,
    IndustryLeadStocks,
)
from data_provider.base import DataFetcherManager


logger = logging.getLogger(__name__)


# 同花顺行业名称 -> 申万行业名称映射表
# 用于处理两种行业分类体系的名称差异
INDUSTRY_NAME_MAPPING = {
    '元件': '元器件',           # 同花顺"元件"对应申万"元器件"
    'IT服务': 'IT设备',         # 同花顺"IT服务"对应申万"IT设备"
    '电池': '电池',             # 可能需要映射到多个申万行业
    '化学制药': '化学制药',     # 名称一致
    '半导体': '半导体',         # 名称一致
    '通信设备': '通信设备',     # 名称一致
}


def normalize_industry_name(industry_name: str) -> str:
    """
    Normalize industry name for better matching between THS and SW classifications
    
    Args:
        industry_name: Industry name from THS classification
    
    Returns:
        Normalized industry name that can match SW classification
    """
    # Direct mapping from the table
    if industry_name in INDUSTRY_NAME_MAPPING:
        return INDUSTRY_NAME_MAPPING[industry_name]
    
    # Fuzzy matching: remove common suffix characters that cause mismatches
    # e.g., "元件" -> "元器件", "设备" vs "备"
    normalized = industry_name
    
    # Remove common suffix differences
    suffix_mappings = [
        ('元件', '元器件'),
        ('设备', '备'),
    ]
    
    for ths_suffix, sw_suffix in suffix_mappings:
        if normalized == ths_suffix:
            normalized = sw_suffix
            break
    
    return normalized


class IndustryMoneyflowTracker:
    """
    板块资金流向追踪器
    
    提供板块资金流向的完整追踪、分析、预警功能
    """
    
    def __init__(self, fetcher_manager: Optional[DataFetcherManager] = None):
        """
        初始化板块资金流向追踪器
        
        Args:
            fetcher_manager: 数据获取管理器（可选，如果不提供会自动创建）
        """
        self.fetcher_manager = fetcher_manager or DataFetcherManager()
        self.db = get_db()
    
    def save_daily_moneyflow(self, trade_date: Optional[date] = None) -> Dict[str, Any]:
        """
        保存每日板块资金流向数据
        
        Args:
            trade_date: 交易日期（可选，默认为今天）
        
        Returns:
            保存结果统计
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块资金追踪] 开始保存 {trade_date} 的板块资金流向数据...")
        
        # 获取所有板块的资金流向数据
        moneyflow_data = self.fetcher_manager.get_industry_moneyflow()
        
        if not moneyflow_data or 'industries' not in moneyflow_data:
            logger.warning(f"[板块资金追踪] 获取板块资金流向数据失败")
            return {'success': False, 'message': '获取数据失败', 'saved_count': 0}
        
        industries = moneyflow_data['industries']
        total_count = len(industries)
        
        # 保存到数据库
        saved_count = 0
        for ind in industries:
            try:
                # 提取数据
                industry_name = ind.get('industry', '未知')
                net_amount = ind.get('net_amount', 0)
                net_buy_amount = ind.get('net_buy_amount', 0)
                net_sell_amount = ind.get('net_sell_amount', 0)
                pct_change = ind.get('pct_change', 0)
                rank = ind.get('rank', 0)
                lead_stock = ind.get('lead_stock', '')
                lead_stock_name = ind.get('lead_stock_name', '')
                lead_stock_change = ind.get('lead_stock_change', 0)
                
                # 创建记录
                record = IndustryMoneyflowDaily(
                    industry_name=industry_name,
                    trade_date=trade_date,
                    net_amount=net_amount,
                    net_buy_amount=net_buy_amount,
                    net_sell_amount=net_sell_amount,
                    pct_change=pct_change,
                    rank=rank,
                    total_industries=total_count,
                    lead_stock=lead_stock,
                    lead_stock_name=lead_stock_name,
                    lead_stock_change=lead_stock_change,
                    data_source=moneyflow_data.get('data_source', 'unknown'),
                )
                
                # 保存到数据库（使用 merge 避免重复）
                with self.db.get_session() as session:
                    existing = session.query(IndustryMoneyflowDaily).filter(
                        and_(
                            IndustryMoneyflowDaily.industry_name == industry_name,
                            IndustryMoneyflowDaily.trade_date == trade_date,
                        )
                    ).first()
                    
                    if existing:
                        # 更新现有记录
                        existing.net_amount = net_amount
                        existing.net_buy_amount = net_buy_amount
                        existing.net_sell_amount = net_sell_amount
                        existing.pct_change = pct_change
                        existing.rank = rank
                        existing.lead_stock = lead_stock
                        existing.lead_stock_name = lead_stock_name
                        existing.lead_stock_change = lead_stock_change
                        existing.data_source = moneyflow_data.get('data_source', 'unknown')
                        existing.updated_at = datetime.now()
                        logger.debug(f"[板块资金追踪] 更新板块 {industry_name} 数据")
                    else:
                        # 添加新记录
                        session.add(record)
                        logger.debug(f"[板块资金追踪] 新增板块 {industry_name} 数据")
                    
                    session.commit()
                    saved_count += 1
                
            except Exception as e:
                logger.error(f"[板块资金追踪] 保存板块 {industry_name} 数据失败: {e}")
                continue
        
        logger.info(f"[板块资金追踪] 成功保存 {saved_count}/{total_count} 个板块的资金流向数据")
        
        return {
            'success': True,
            'message': f'成功保存 {saved_count} 个板块数据',
            'saved_count': saved_count,
            'total_count': total_count,
        }
    
    def get_industry_moneyflow_history(
        self, 
        industry_name: str, 
        days: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取板块资金流向历史趋势
        
        Args:
            industry_name: 板块名称
            days: 查询天数（默认10天）
        
        Returns:
            历史数据列表（按日期倒序）
        """
        logger.info(f"[板块资金追踪] 获取板块 {industry_name} 最近 {days} 天的资金流向历史...")
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        with self.db.get_session() as session:
            records = session.query(IndustryMoneyflowDaily).filter(
                and_(
                    IndustryMoneyflowDaily.industry_name == industry_name,
                    IndustryMoneyflowDaily.trade_date >= start_date,
                    IndustryMoneyflowDaily.trade_date <= end_date,
                )
            ).order_by(desc(IndustryMoneyflowDaily.trade_date)).all()
            
            history = [record.to_dict() for record in records]
        
        logger.info(f"[板块资金追踪] 查询到 {len(history)} 条历史数据")
        
        return history
    
    def get_top_industries(
        self, 
        trade_date: Optional[date] = None,
        limit: int = 10,
        sort_by: str = 'net_amount',
        direction: str = 'inflow'
    ) -> List[Dict[str, Any]]:
        """
        获取Top N板块排名
        
        Args:
            trade_date: 交易日期（可选，默认为今天）
            limit: 返回数量（默认10）
            sort_by: 排序字段（net_amount, pct_change, rank）
            direction: 流向方向（inflow=流入, outflow=流出）
        
        Returns:
            Top N板块列表
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块资金追踪] 获取 {trade_date} Top {limit} {direction} 板块...")
        
        with self.db.get_session() as session:
            query = session.query(IndustryMoneyflowDaily).filter(
                IndustryMoneyflowDaily.trade_date == trade_date
            )
            
            # 根据流向方向过滤
            if direction == 'inflow':
                query = query.filter(IndustryMoneyflowDaily.net_amount > 0)
            elif direction == 'outflow':
                query = query.filter(IndustryMoneyflowDaily.net_amount < 0)
            
            # 排序
            if sort_by == 'net_amount':
                if direction == 'inflow':
                    query = query.order_by(desc(IndustryMoneyflowDaily.net_amount))
                else:
                    query = query.order_by(IndustryMoneyflowDaily.net_amount)  # 负数越小越好
            elif sort_by == 'pct_change':
                query = query.order_by(desc(IndustryMoneyflowDaily.pct_change))
            elif sort_by == 'rank':
                query = query.order_by(IndustryMoneyflowDaily.rank)
            
            records = query.limit(limit).all()
            top_industries = [record.to_dict() for record in records]
        
        logger.info(f"[板块资金追踪] 查询到 {len(top_industries)} 个板块")
        
        return top_industries
    
    def detect_moneyflow_alerts(
        self, 
        min_days: int = 3,
        threshold_amount: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        检测板块资金流向预警
        
        Args:
            min_days: 连续天数阈值（默认3天）
            threshold_amount: 金额阈值（默认5亿）
        
        Returns:
            预警列表
        """
        logger.info(f"[板块资金追踪] 开始检测板块资金流向预警（连续{min_days}天，金额{threshold_amount}亿）...")
        
        alerts = []
        
        # 获取最近min_days+2天的数据（留出buffer）
        end_date = date.today()
        start_date = end_date - timedelta(days=min_days + 2)
        
        with self.db.get_session() as session:
            # 获取所有板块列表
            industries = session.query(IndustryMoneyflowDaily.industry_name).filter(
                IndustryMoneyflowDaily.trade_date >= start_date,
                IndustryMoneyflowDaily.trade_date <= end_date,
            ).distinct().all()
            
            for industry_tuple in industries:
                industry_name = industry_tuple[0]
                
                # 获取该板块最近min_days+2天的数据
                records = session.query(IndustryMoneyflowDaily).filter(
                    and_(
                        IndustryMoneyflowDaily.industry_name == industry_name,
                        IndustryMoneyflowDaily.trade_date >= start_date,
                        IndustryMoneyflowDaily.trade_date <= end_date,
                    )
                ).order_by(desc(IndustryMoneyflowDaily.trade_date)).limit(min_days + 2).all()
                
                if len(records) < min_days:
                    continue
                
                # 检查连续流入
                inflow_days = 0
                total_inflow = 0
                for record in records[:min_days]:
                    if record.net_amount > threshold_amount:
                        inflow_days += 1
                        total_inflow += record.net_amount
                
                if inflow_days >= min_days:
                    avg_inflow = total_inflow / inflow_days
                    alert = {
                        'industry_name': industry_name,
                        'alert_date': records[0].trade_date,
                        'alert_type': 'continuous_inflow',
                        'alert_level': self._calculate_alert_level(inflow_days, avg_inflow),
                        'consecutive_days': inflow_days,
                        'total_amount': total_inflow,
                        'avg_amount': avg_inflow,
                        'trigger_condition': f'连续{inflow_days}天净流入>{threshold_amount}亿',
                        'recommendation': f'板块{industry_name}连续{inflow_days}天资金流入，建议关注龙头股',
                        'lead_stock': records[0].lead_stock,
                        'lead_stock_name': records[0].lead_stock_name,
                    }
                    alerts.append(alert)
                    logger.info(f"[板块资金追踪] 发现板块 {industry_name} 连续流入预警：{inflow_days}天，累计{total_inflow:.2f}亿")
                
                # 检查连续流出
                outflow_days = 0
                total_outflow = 0
                for record in records[:min_days]:
                    if record.net_amount < -threshold_amount:
                        outflow_days += 1
                        total_outflow += record.net_amount
                
                if outflow_days >= min_days:
                    avg_outflow = total_outflow / outflow_days
                    alert = {
                        'industry_name': industry_name,
                        'alert_date': records[0].trade_date,
                        'alert_type': 'continuous_outflow',
                        'alert_level': self._calculate_alert_level(outflow_days, abs(avg_outflow)),
                        'consecutive_days': outflow_days,
                        'total_amount': total_outflow,
                        'avg_amount': avg_outflow,
                        'trigger_condition': f'连续{outflow_days}天净流出<{threshold_amount}亿',
                        'recommendation': f'板块{industry_name}连续{outflow_days}天资金流出，建议规避或减仓',
                        'lead_stock': records[0].lead_stock,
                        'lead_stock_name': records[0].lead_stock_name,
                    }
                    alerts.append(alert)
                    logger.info(f"[板块资金追踪] 发现板块 {industry_name} 连续流出预警：{outflow_days}天，累计{total_outflow:.2f}亿")
        
        logger.info(f"[板块资金追踪] 检测到 {len(alerts)} 个板块资金流向预警")
        
        return alerts
    
    def _calculate_alert_level(self, days: int, amount: float) -> str:
        """
        计算预警级别
        
        Args:
            days: 连续天数
            amount: 金额（亿）
        
        Returns:
            预警级别（high/medium/low）
        """
        if days >= 5 and amount >= 10:
            return 'high'
        elif days >= 4 or amount >= 8:
            return 'medium'
        else:
            return 'low'
    
    def get_lead_stocks_in_continuous_inflow_industries(
        self, 
        min_days: int = 3,
        threshold_amount: float = 5.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        筛选连续流入板块的龙头股
        
        Args:
            min_days: 连续流入天数阈值（默认3天）
            threshold_amount: 金额阈值（默认5亿）
            limit: 返回数量（默认10）
        
        Returns:
            龙头股列表
        """
        logger.info(f"[板块资金追踪] 筛选连续{min_days}天流入板块的龙头股...")
        
        # 首先获取连续流入的板块
        alerts = self.detect_moneyflow_alerts(min_days=min_days, threshold_amount=threshold_amount)
        inflow_alerts = [a for a in alerts if a['alert_type'] == 'continuous_inflow']
        
        if not inflow_alerts:
            logger.info(f"[板块资金追踪] 未发现连续流入板块")
            return []
        
        # 提取龙头股信息
        lead_stocks = []
        for alert in inflow_alerts[:limit]:
            if alert['lead_stock'] and alert['lead_stock_name']:
                lead_stock_info = {
                    'stock_code': alert['lead_stock'],
                    'stock_name': alert['lead_stock_name'],
                    'industry_name': alert['industry_name'],
                    'consecutive_days': alert['consecutive_days'],
                    'total_inflow': alert['total_amount'],
                    'avg_inflow': alert['avg_amount'],
                    'alert_level': alert['alert_level'],
                    'recommendation': alert['recommendation'],
                }
                lead_stocks.append(lead_stock_info)
                logger.info(f"[板块资金追踪] 发现龙头股 {alert['lead_stock_name']}（{alert['lead_stock']}）在板块 {alert['industry_name']}")
        
        logger.info(f"[板块资金追踪] 筛选出 {len(lead_stocks)} 个龙头股")
        
        return lead_stocks
    
    def analyze_industry_rotation(
        self, 
        trade_date: Optional[date] = None,
        threshold_amount: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        分析板块轮动（资金在不同板块间的流动）
        
        Args:
            trade_date: 交易日期（可选，默认为今天）
            threshold_amount: 轮动金额阈值（默认10亿）
        
        Returns:
            板块轮动分析结果
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块资金追踪] 分析 {trade_date} 的板块轮动...")
        
        # 获取当日的Top流入和流出板块
        top_inflow = self.get_top_industries(trade_date, limit=5, direction='inflow')
        top_outflow = self.get_top_industries(trade_date, limit=5, direction='outflow')
        
        if not top_inflow or not top_outflow:
            logger.info(f"[板块资金追踪] 数据不足，无法分析板块轮动")
            return []
        
        rotations = []
        
        # 分析资金从流出板块流向流入板块的情况
        for outflow in top_outflow:
            for inflow in top_inflow:
                # 计算轮动金额（流出金额的绝对值）
                rotation_amount = abs(outflow['net_amount'])
                
                if rotation_amount >= threshold_amount:
                    # 判断轮动强度
                    rotation_type = self._calculate_rotation_type(rotation_amount)
                    
                    rotation = {
                        'analysis_date': trade_date,
                        'outflow_industry': outflow['industry_name'],
                        'outflow_amount': outflow['net_amount'],
                        'inflow_industry': inflow['industry_name'],
                        'inflow_amount': inflow['net_amount'],
                        'rotation_amount': rotation_amount,
                        'rotation_type': rotation_type,
                        'rotation_reason': f'资金从{outflow["industry_name"]}流出{abs(outflow["net_amount"]):.2f}亿，流入{inflow["industry_name"]}{inflow["net_amount"]:.2f}亿',
                        'lead_stock_outflow': outflow['lead_stock'],
                        'lead_stock_outflow_name': outflow['lead_stock_name'],
                        'lead_stock_inflow': inflow['lead_stock'],
                        'lead_stock_inflow_name': inflow['lead_stock_name'],
                    }
                    rotations.append(rotation)
                    logger.info(f"[板块资金追踪] 发现板块轮动：{outflow['industry_name']} → {inflow['industry_name']}, 金额{rotation_amount:.2f}亿")
        
        # 保存轮动分析结果
        self._save_rotation_analysis(rotations)
        
        logger.info(f"[板块资金追踪] 分析到 {len(rotations)} 个板块轮动")
        
        return rotations
    
    def _calculate_rotation_type(self, amount: float) -> str:
        """
        计算轮动强度
        
        Args:
            amount: 轮动金额（亿）
        
        Returns:
            轮动类型（strong/medium/weak）
        """
        if amount >= 20:
            return 'strong'
        elif amount >= 10:
            return 'medium'
        else:
            return 'weak'
    
    def _save_rotation_analysis(self, rotations: List[Dict[str, Any]]) -> None:
        """
        保存板块轮动分析结果
        
        Args:
            rotations: 轮动分析结果列表
        """
        for rotation in rotations:
            try:
                record = IndustryRotation(
                    analysis_date=rotation['analysis_date'],
                    outflow_industry=rotation['outflow_industry'],
                    outflow_amount=rotation['outflow_amount'],
                    inflow_industry=rotation['inflow_industry'],
                    inflow_amount=rotation['inflow_amount'],
                    rotation_amount=rotation['rotation_amount'],
                    rotation_type=rotation['rotation_type'],
                    rotation_reason=rotation['rotation_reason'],
                    lead_stock_outflow=rotation['lead_stock_outflow'],
                    lead_stock_outflow_name=rotation['lead_stock_outflow_name'],
                    lead_stock_inflow=rotation['lead_stock_inflow'],
                    lead_stock_inflow_name=rotation['lead_stock_inflow_name'],
                )
                
                with self.db.get_session() as session:
                    session.add(record)
                    session.commit()
                
            except Exception as e:
                logger.error(f"[板块资金追踪] 保存板块轮动分析失败: {e}")
    
    def get_industry_ranking_changes(
        self, 
        industry_name: str,
        days: int = 5
    ) -> Dict[str, Any]:
        """
        获取板块排名变化
        
        Args:
            industry_name: 板块名称
            days: 查询天数（默认5天）
        
        Returns:
            排名变化分析
        """
        logger.info(f"[板块资金追踪] 分析板块 {industry_name} 最近 {days} 天的排名变化...")
        
        history = self.get_industry_moneyflow_history(industry_name, days=days)
        
        if len(history) < 2:
            return {'message': '数据不足，无法分析排名变化'}
        
        # 分析排名变化趋势
        ranks = [h['rank'] for h in history if h['rank'] > 0]
        
        if not ranks:
            return {'message': '排名数据缺失'}
        
        rank_change = ranks[0] - ranks[-1]  # 最新排名 - 最早排名
        
        if rank_change < 0:
            trend = 'up'  # 排名上升（数字变小）
            message = f'板块{industry_name}排名上升{abs(rank_change)}位，表现向好'
        elif rank_change > 0:
            trend = 'down'  # 排名下降（数字变大）
            message = f'板块{industry_name}排名下降{rank_change}位，表现走弱'
        else:
            trend = 'stable'
            message = f'板块{industry_name}排名稳定，维持在{ranks[0]}位'
        
        result = {
            'industry_name': industry_name,
            'current_rank': ranks[0],
            'previous_rank': ranks[-1],
            'rank_change': rank_change,
            'trend': trend,
            'message': message,
            'history': history,
        }
        
        logger.info(f"[板块资金追踪] 板块 {industry_name} 排名变化：{rank_change}位，趋势={trend}")
        
        return result
    
    def get_top3_lead_stocks_per_industry(
        self,
        industry_name: str,
        trade_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定板块的前3龙头股（按涨跌幅排序）
        
        Args:
            industry_name: 板块名称
            trade_date: 交易日期（可选，默认为今天）
        
        Returns:
            前3龙头股列表（包含股票代码、名称、涨跌幅等信息）
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块资金追踪] 获取板块 {industry_name} 的前3龙头股...")
        
        try:
            # Step 1: 获取板块成分股列表
            # 使用stock_basic接口获取所有股票的基础信息（包括行业分类）
            import tushare as ts
            
            pro = ts.pro_api()
            
            # 获取所有上市股票的基础信息
            stock_basic_df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry,market,list_date')
            
            if stock_basic_df is None or stock_basic_df.empty:
                logger.warning(f"[板块资金追踪] 未获取到股票基础数据")
                return []
            
            # Normalize industry name for better matching
            normalized_industry_name = normalize_industry_name(industry_name)
            logger.info(f"[板块资金追踪] 板块名称映射: '{industry_name}' -> '{normalized_industry_name}'")
            
            # 筛选出指定板块的股票（使用规范化后的行业名称）
            # Try both original and normalized name
            industry_stocks = stock_basic_df[
                stock_basic_df['industry'].str.contains(industry_name, na=False) |
                stock_basic_df['industry'].str.contains(normalized_industry_name, na=False)
            ]
            
            if industry_stocks.empty:
                logger.warning(f"[板块资金追踪] 板块 {industry_name} (规范化: {normalized_industry_name}) 未找到成分股")
                return []
            
            stock_codes = industry_stocks['ts_code'].tolist()
            logger.info(f"[板块资金追踪] 板块 {industry_name} 共有 {len(stock_codes)} 只成分股")
            
            # Step 2: 获取今日行情数据
            trade_date_str = trade_date.strftime('%Y%m%d')
            
            # 批量获取股票行情（每次最多100只，需要分批）
            all_daily_data = []
            batch_size = 100
            
            for i in range(0, len(stock_codes), batch_size):
                batch_codes = stock_codes[i:i+batch_size]
                
                try:
                    # 使用query接口批量查询行情数据
                    daily_df = pro.query('daily', trade_date=trade_date_str, ts_code=','.join(batch_codes))
                    
                    if daily_df is not None and not daily_df.empty:
                        all_daily_data.append(daily_df)
                    
                    # 避免API频率限制，每批请求后暂停0.5秒
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"[板块资金追踪] 获取第 {i//batch_size + 1} 批股票行情失败: {e}")
                    continue
            
            # 合合所有行情数据
            if not all_daily_data:
                logger.warning(f"[板块资金追踪] 未获取到板块 {industry_name} 的行情数据")
                return []
            
            import pandas as pd
            combined_df = pd.concat(all_daily_data, ignore_index=True)
            
            # Step 3: 根据涨跌幅排序，取前3
            # 注意：daily接口返回的涨跌幅字段名是pct_chg，而不是pct_change
            if 'pct_chg' not in combined_df.columns:
                logger.warning(f"[板块资金追踪] 行情数据中缺少pct_chg字段")
                return []
            
            # 按涨跌幅降序排序
            sorted_df = combined_df.sort_values('pct_chg', ascending=False).head(3)
            
            # Step 4: 构建返回结果
            top3_stocks = []
            
            for i, (_, row) in enumerate(sorted_df.iterrows(), 1):
                ts_code = row.get('ts_code', '')
                # 从industry_stocks中获取股票名称
                stock_name = industry_stocks[industry_stocks['ts_code'] == ts_code]['name'].values[0] if len(industry_stocks[industry_stocks['ts_code'] == ts_code]) > 0 else '未知'
                
                stock_info = {
                    'rank': i,
                    'stock_code': ts_code,
                    'stock_name': stock_name,
                    'pct_change': row.get('pct_chg', 0),  # 使用pct_chg字段
                    'close': row.get('close', 0),
                    'vol': row.get('vol', 0),
                    'amount': row.get('amount', 0),
                }
                
                top3_stocks.append(stock_info)
                logger.info(f"[板块资金追踪] 第{i}龙头股: {stock_name}({ts_code}), 涨跌={row.get('pct_chg', 0):.2f}%")
            
            logger.info(f"[板块资金追踪] 成功获取板块 {industry_name} 的前3龙头股")
            
            return top3_stocks
            
        except Exception as e:
            logger.error(f"[板块资金追踪] 获取板块 {industry_name} 的前3龙头股失败: {e}")
            return []

    def get_top3_moneyflow_stocks_per_industry(
        self,
        industry_name: str,
        trade_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top 3 stocks with highest money inflow in specified industry (Popularity leaders)
        
        Args:
            industry_name: Industry name
            trade_date: Trade date (optional, default to today)
        
        Returns:
            List of top 3 stocks with highest money inflow (including stock code, name, inflow amount, etc.)
        """
        if trade_date is None:
            trade_date = date.today()
        
        logger.info(f"[板块资金追踪] 获取板块 {industry_name} 的资金流入前3龙头股...")
        
        try:
            # Step 1: Get industry constituent stocks
            import tushare as ts
            
            pro = ts.pro_api()
            
            # Get all listed stocks basic info
            stock_basic_df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry,market,list_date')
            
            if stock_basic_df is None or stock_basic_df.empty:
                logger.warning(f"[板块资金追踪] 未获取到股票基础数据")
                return []
            
            # Normalize industry name for better matching
            normalized_industry_name = normalize_industry_name(industry_name)
            logger.info(f"[板块资金追踪] 板块名称映射: '{industry_name}' -> '{normalized_industry_name}'")
            
            # Filter stocks in specified industry (using both original and normalized name)
            industry_stocks = stock_basic_df[
                stock_basic_df['industry'].str.contains(industry_name, na=False) |
                stock_basic_df['industry'].str.contains(normalized_industry_name, na=False)
            ]
            
            if industry_stocks.empty:
                logger.warning(f"[板块资金追踪] 板块 {industry_name} (规范化: {normalized_industry_name}) 未找到成分股")
                return []
            
            stock_codes = industry_stocks['ts_code'].tolist()
            logger.info(f"[板块资金追踪] 板块 {industry_name} 共有 {len(stock_codes)} 只成分股")
            
            # Step 2: Get today's moneyflow data for these stocks
            trade_date_str = trade_date.strftime('%Y%m%d')
            
            # Get moneyflow data for all stocks on this date
            moneyflow_df = pro.moneyflow(trade_date=trade_date_str)
            
            if moneyflow_df is None or moneyflow_df.empty:
                logger.warning(f"[板块资金追踪] 未获取到 {trade_date} 的资金流向数据")
                return []
            
            # Filter moneyflow data for industry stocks
            industry_moneyflow = moneyflow_df[moneyflow_df['ts_code'].isin(stock_codes)]
            
            if industry_moneyflow.empty:
                logger.warning(f"[板块资金追踪] 板块 {industry_name} 未找到资金流向数据")
                return []
            
            # Step 3: Sort by net money inflow amount and get top 3
            # Note: net_mf_amount is the net inflow amount (in万元, need to convert to 亿)
            if 'net_mf_amount' not in industry_moneyflow.columns:
                logger.warning(f"[板块资金追踪] 资金流向数据中缺少net_mf_amount字段")
                return []
            
            # Sort by net inflow amount (descending)
            sorted_df = industry_moneyflow.sort_values('net_mf_amount', ascending=False).head(3)
            
            # Step 4: Build result list
            top3_stocks = []
            
            for i, (_, row) in enumerate(sorted_df.iterrows(), 1):
                ts_code = row.get('ts_code', '')
                # Get stock name from industry_stocks
                stock_name = industry_stocks[industry_stocks['ts_code'] == ts_code]['name'].values[0] if len(industry_stocks[industry_stocks['ts_code'] == ts_code]) > 0 else '未知'
                
                # Convert net_mf_amount from万元 to亿
                net_mf_amount_yi = row.get('net_mf_amount', 0) / 10000  # Convert to 亿
                
                stock_info = {
                    'rank': i,
                    'stock_code': ts_code,
                    'stock_name': stock_name,
                    'net_mf_amount': net_mf_amount_yi,  # Net inflow amount (in 亿)
                    'net_mf_vol': row.get('net_mf_vol', 0),  # Net inflow volume (in手)
                    'buy_elg_amount': row.get('buy_elg_amount', 0) / 10000,  # Super large buy amount (in 亿)
                    'sell_elg_amount': row.get('sell_elg_amount', 0) / 10000,  # Super large sell amount (in 亿)
                }
                
                top3_stocks.append(stock_info)
                logger.info(f"[板块资金追踪] 第{i}资金流入龙头: {stock_name}({ts_code}), 净流入={net_mf_amount_yi:.2f}亿")
            
            logger.info(f"[板块资金追踪] 成功获取板块 {industry_name} 的资金流入前3龙头股")
            
            return top3_stocks
            
        except Exception as e:
            logger.error(f"[板块资金追踪] 获取板块 {industry_name} 的资金流入前3龙头股失败: {e}")
            return []