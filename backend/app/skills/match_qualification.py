import json
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Literal

from app.models.qualification import (
    CertificateStatus,
    CompanyProfile,
    PerformanceRecord,
    PersonnelCertificate,
    QualificationCertificate,
)
from app.schemas.skills.match import MatchItem, MatchReport, RiskLevel
from app.schemas.skills.parse import ParseResult, QualificationItem


logger = logging.getLogger(__name__)

_NORMALIZE_PATTERN = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")
_AMOUNT_PATTERN = re.compile(
    r"(?:注册资本|合同金额|项目金额|单项金额|金额|投资额|造价|规模|预算)"
    r"[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*(亿元|亿|万元|万|元)"
)
_COUNT_PATTERN = re.compile(r"([0-9]+|[一二三四五六七八九十两]+)\s*(项|个|名|人|位)")
_RECENT_YEARS_PATTERN = re.compile(r"近\s*([0-9]+|[一二三四五六七八九十两]+)\s*年")
_ESTABLISHED_YEARS_PATTERN = re.compile(
    r"(?:成立|经营)\s*(?:满|不少于|至少)?\s*"
    r"([0-9]+|[一二三四五六七八九十两]+)\s*年"
)
_GENERIC_TERMS = {
    "具有",
    "具备",
    "提供",
    "投标人",
    "供应商",
    "申请人",
    "要求",
    "相关",
    "类似",
    "项目",
    "业绩",
    "证书",
    "资质",
    "有效",
    "以上",
    "不少于",
    "至少",
    "人员",
}
_SPECIALTY_KEYWORDS = {
    "建筑工程",
    "市政公用工程",
    "机电工程",
    "公路工程",
    "水利水电工程",
    "通信与广电工程",
    "矿业工程",
    "铁路工程",
    "港口与航道工程",
    "民航机场工程",
    "电力工程",
    "石油化工工程",
    "冶金工程",
    "钢结构工程",
    "消防设施工程",
    "建筑装修装饰工程",
    "电子与智能化工程",
    "环保工程",
}


@dataclass(slots=True, frozen=True)
class CompanyKnowledgeBase:
    certificates: list[QualificationCertificate]
    performances: list[PerformanceRecord]
    personnel: list[PersonnelCertificate]
    companies: list[CompanyProfile]


@dataclass(slots=True, frozen=True)
class EvaluatedItem:
    bucket: Literal["matched", "missing", "risk"]
    item: MatchItem
    score: float
    weight: float


class MatchQualificationSkill:
    """仅使用结构化字段和确定性规则执行资质匹配。"""

    EXPIRY_WARNING_DAYS = 90

    def run(
        self,
        parse_result: ParseResult,
        knowledge_base: CompanyKnowledgeBase,
    ) -> MatchReport:
        requirements = parse_result.qualifications
        if not requirements:
            return MatchReport(
                overall_match_score=None,
                summary="标书解析结果中没有可用于自动匹配的资格要求",
                suggestions=["请核对标书解析结果，必要时补充结构化资格要求后重新匹配"],
            )

        evaluated: list[EvaluatedItem] = []
        for requirement in requirements:
            category = _normalize_category(requirement)
            if category == "资质":
                result = self._match_certificate(requirement, knowledge_base.certificates)
            elif category == "业绩":
                result = self._match_performance(requirement, knowledge_base.performances)
            elif category == "人员":
                result = self._match_personnel(requirement, knowledge_base.personnel)
            elif category == "财务":
                result = self._match_financial(requirement, knowledge_base.companies)
            else:
                result = self._match_other(requirement, knowledge_base.companies)
            evaluated.append(result)
            logger.info(
                "资质匹配：category=%s bucket=%s requirement=%s company_status=%s",
                category,
                result.bucket,
                requirement.description[:200],
                result.item.company_status[:200],
            )

        matched_items = [item.item for item in evaluated if item.bucket == "matched"]
        missing_items = [item.item for item in evaluated if item.bucket == "missing"]
        risk_items = [item.item for item in evaluated if item.bucket == "risk"]
        total_weight = sum(item.weight for item in evaluated)
        weighted_score = sum(item.score * item.weight for item in evaluated)
        score = round(weighted_score / total_weight * 100, 2) if total_weight else None

        summary = self._build_summary(
            score,
            len(matched_items),
            len(missing_items),
            len(risk_items),
        )
        suggestions = self._build_suggestions(missing_items, risk_items)
        return MatchReport(
            overall_match_score=score,
            summary=summary,
            matched_items=matched_items,
            missing_items=missing_items,
            risk_items=risk_items,
            suggestions=suggestions,
        )

    def _match_certificate(
        self,
        requirement: QualificationItem,
        certificates: list[QualificationCertificate],
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        required_specialties = _extract_specialties(description)
        candidates = [
            certificate
            for certificate in certificates
            if _record_matches_requirement(
                description,
                certificate.name,
                certificate.specialty,
            )
            and _specialty_satisfies(
                required_specialties,
                certificate.name,
                certificate.specialty,
            )
        ]
        weight = _requirement_weight(requirement)
        if not candidates:
            return _missing(
                requirement,
                "资质",
                "知识库中未找到名称或专业匹配的企业资质证书",
                "请补充对应资质证书，或人工确认招标要求与证书名称的对应关系",
                weight,
            )

        level_candidates = [
            item for item in candidates if _certificate_level_satisfies(description, item.level)
        ]
        if not level_candidates:
            levels = "、".join(
                f"{item.name}（{item.level or '未填写等级'}）" for item in candidates[:5]
            )
            return _missing(
                requirement,
                "资质",
                f"找到相关证书，但等级不满足或未填写：{levels}",
                "核验证书等级是否达到招标文件要求",
                weight,
            )

        current = [item for item in level_candidates if item.is_currently_valid]
        if not current:
            states = "、".join(
                f"{item.name}（状态 {item.status.value}，有效期至 {item.valid_to or '未填写'}）"
                for item in level_candidates[:5]
            )
            return _missing(
                requirement,
                "资质",
                f"相关证书均不在有效状态：{states}",
                "更新、延续或重新录入有效资质证书",
                weight,
            )

        best = max(current, key=lambda item: item.valid_to or date.max)
        status = (
            f"已匹配证书：{best.name}，等级 {best.level or '未注明'}，"
            f"证书编号 {best.cert_number or '未填写'}，有效期至 {best.valid_to or '长期/未填写'}"
        )
        if _expires_soon(best.valid_to, self.EXPIRY_WARNING_DAYS):
            return _risk(
                requirement,
                "资质",
                status,
                True,
                RiskLevel.MEDIUM,
                "证书将在 90 天内到期，请确认投标及履约期间持续有效",
                weight,
                score=0.75,
            )
        return _matched(requirement, "资质", status, weight)

    def _match_performance(
        self,
        requirement: QualificationItem,
        performances: list[PerformanceRecord],
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        weight = _requirement_weight(requirement)
        required_amount = _extract_amount(description)
        required_count = _extract_count(description, unit="项") or 1
        recent_years = _extract_recent_years(description)
        cutoff = (
            _years_ago(recent_years)
            if recent_years
            else None
        )
        requires_completed = "完成" in description or "已完" in description

        similar = [
            item
            for item in performances
            if _performance_matches_requirement(description, item)
        ]
        if not similar and performances and _only_generic_performance_requirement(description):
            return _risk(
                requirement,
                "业绩",
                f"知识库中有 {len(performances)} 条业绩，但要求仅描述为类似业绩，无法确定项目类型是否一致",
                False,
                RiskLevel.HIGH,
                "请人工核验业绩相似性，并完善 related_qualification 或 description 字段",
                weight,
                score=0.25,
            )

        qualified: list[PerformanceRecord] = []
        boundary: list[str] = []
        for item in similar:
            if requires_completed and not item.is_completed:
                continue
            if cutoff:
                record_date = item.end_date or item.start_date
                if record_date is None:
                    boundary.append(f"{item.project_name} 未填写项目日期")
                    continue
                if record_date < cutoff:
                    continue
                if record_date <= cutoff + timedelta(days=90):
                    boundary.append(f"{item.project_name} 接近近 {recent_years} 年边界")
            if required_amount is not None:
                if item.currency.upper() != "CNY":
                    boundary.append(f"{item.project_name} 使用 {item.currency}，未自动换算")
                    continue
                if item.project_amount is None:
                    boundary.append(f"{item.project_name} 未填写项目金额")
                    continue
                if item.project_amount < required_amount:
                    continue
                if item.project_amount <= required_amount * Decimal("1.05"):
                    boundary.append(f"{item.project_name} 金额接近要求下限")
            qualified.append(item)

        if len(qualified) < required_count:
            status = (
                f"找到 {len(similar)} 条类型相关业绩，其中 {len(qualified)} 条满足已知硬条件，"
                f"要求至少 {required_count} 条"
            )
            if boundary:
                status += "；待核验：" + "；".join(boundary[:3])
            return _missing(
                requirement,
                "业绩",
                status,
                "补充满足项目类型、时间、金额和完成状态要求的业绩材料",
                weight,
            )

        names = "、".join(item.project_name for item in qualified[:5])
        status = f"已有 {len(qualified)} 条业绩满足已知硬条件：{names}"
        if boundary:
            return _risk(
                requirement,
                "业绩",
                status + "；另有边界项：" + "；".join(boundary[:3]),
                True,
                RiskLevel.LOW,
                "已满足数量要求，但建议复核时间、金额边界及证明材料",
                weight,
                score=0.85,
            )
        return _matched(requirement, "业绩", status, weight)

    def _match_personnel(
        self,
        requirement: QualificationItem,
        personnel: list[PersonnelCertificate],
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        weight = _requirement_weight(requirement)
        required_count = _extract_personnel_count(description) or 1
        required_specialties = _extract_specialties(description)
        related = [
            item
            for item in personnel
            if _record_matches_requirement(
                description,
                item.cert_type,
                item.specialty,
            )
            and _specialty_satisfies(
                required_specialties,
                item.cert_type,
                item.specialty,
            )
        ]
        current = [item for item in related if item.is_currently_valid]
        if len(current) < required_count:
            off_job = sum(not item.is_on_job for item in related)
            expired = sum(
                item.valid_to is not None and item.valid_to < date.today()
                for item in related
            )
            return _missing(
                requirement,
                "人员",
                f"找到 {len(related)} 本相关人员证书，当前有效且在职 {len(current)} 本，"
                f"要求至少 {required_count} 人；离职 {off_job} 人，过期 {expired} 本",
                "补充满足专业、证书类型、有效期和在职要求的人员",
                weight,
            )

        names = "、".join(
            f"{item.person_name}（{item.cert_type}）" for item in current[:5]
        )
        status = f"当前有 {len(current)} 名有效在职人员满足要求：{names}"
        expiring = [
            item for item in current if _expires_soon(item.valid_to, self.EXPIRY_WARNING_DAYS)
        ]
        if expiring:
            expiring_names = "、".join(item.person_name for item in expiring[:5])
            return _risk(
                requirement,
                "人员",
                status,
                True,
                RiskLevel.MEDIUM,
                f"人员证书将在 90 天内到期：{expiring_names}",
                weight,
                score=0.75,
            )
        return _matched(requirement, "人员", status, weight)

    def _match_financial(
        self,
        requirement: QualificationItem,
        companies: list[CompanyProfile],
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        weight = _requirement_weight(requirement)
        required_amount = _extract_amount(description)
        if "注册资本" in description and required_amount is not None:
            eligible = [
                item
                for item in companies
                if item.registered_capital is not None
                and item.registered_capital >= required_amount
            ]
            if eligible:
                best = max(eligible, key=lambda item: item.registered_capital or Decimal(0))
                return _matched(
                    requirement,
                    "财务",
                    f"{best.company_name} 注册资本为 {best.registered_capital} 元，达到要求",
                    weight,
                )
            known = "、".join(
                f"{item.company_name}：{item.registered_capital or '未填写'} 元"
                for item in companies[:5]
            )
            return _missing(
                requirement,
                "财务",
                f"没有公司主体达到注册资本要求；当前记录：{known or '无公司信息'}",
                "核实并补充公司注册资本信息",
                weight,
            )

        return self._manual_review(requirement, "财务", companies, weight)

    def _match_other(
        self,
        requirement: QualificationItem,
        companies: list[CompanyProfile],
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        weight = _requirement_weight(requirement)
        required_years = _extract_established_years(description)
        if required_years is not None and companies:
            eligible = [
                item
                for item in companies
                if item.establish_date is not None
                and _full_years_since(item.establish_date) >= required_years
            ]
            if eligible:
                best = max(eligible, key=lambda item: _full_years_since(item.establish_date))
                return _matched(
                    requirement,
                    "其他",
                    f"{best.company_name} 已成立 {_full_years_since(best.establish_date)} 年，达到要求",
                    weight,
                )
            return _missing(
                requirement,
                "其他",
                "公司信息中没有主体达到或完整记录所需成立年限",
                "补充并核验公司成立日期",
                weight,
            )
        return self._manual_review(requirement, "其他", companies, weight)

    def _manual_review(
        self,
        requirement: QualificationItem,
        category: str,
        companies: list[CompanyProfile],
        weight: float,
    ) -> EvaluatedItem:
        description = _requirement_text(requirement)
        company_text = " ".join(
            " ".join(
                filter(
                    None,
                    [
                        item.company_name,
                        item.address,
                        json.dumps(item.extra_info, ensure_ascii=False),
                    ],
                )
            )
            for item in companies
        )
        overlap = _keyword_overlap(description, company_text)
        if overlap:
            status = f"公司信息中存在相关关键词：{'、'.join(overlap[:5])}，但缺少专用结构化字段"
        else:
            status = "当前知识库没有足够的结构化字段自动判断该要求"
        return _risk(
            requirement,
            category,
            status,
            False,
            RiskLevel.HIGH if requirement.is_mandatory else RiskLevel.MEDIUM,
            "该项需人工核验原件或补充结构化公司数据",
            weight,
            score=0.25,
        )

    @staticmethod
    def _build_summary(
        score: float | None,
        matched_count: int,
        missing_count: int,
        risk_count: int,
    ) -> str:
        prefix = f"综合匹配分 {score:.2f} 分；" if score is not None else ""
        if missing_count:
            conclusion = "存在明确不满足项，当前不建议直接投标"
        elif risk_count:
            conclusion = "未发现明确缺失项，但存在需要复核的风险"
        else:
            conclusion = "已记录的结构化资格要求均明确满足"
        return (
            f"{prefix}{conclusion}。已满足 {matched_count} 项，"
            f"缺失 {missing_count} 项，风险 {risk_count} 项"
        )

    @staticmethod
    def _build_suggestions(
        missing_items: list[MatchItem],
        risk_items: list[MatchItem],
    ) -> list[str]:
        suggestions: list[str] = []
        if missing_items:
            categories = "、".join(sorted({item.category for item in missing_items}))
            suggestions.append(f"优先补齐或确认以下类别的缺失项：{categories}")
        if any(item.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH} for item in risk_items):
            suggestions.append("投标前逐项复核中高风险要求，并准备对应证明原件")
        if any("到期" in (item.comment or "") for item in risk_items):
            suggestions.append("尽快办理临期证书续期，确认投标和履约期间持续有效")
        if any(item.category == "业绩" for item in missing_items + risk_items):
            suggestions.append("完善业绩的金额、日期、项目类型和证明材料字段")
        if not suggestions:
            suggestions.append("按招标文件清单整理证书、业绩和人员证明材料")
        return suggestions


def _matched(
    requirement: QualificationItem,
    category: str,
    company_status: str,
    weight: float,
) -> EvaluatedItem:
    return EvaluatedItem(
        bucket="matched",
        item=MatchItem(
            category=category,
            requirement=_requirement_text(requirement),
            company_status=company_status,
            is_matched=True,
            risk_level=RiskLevel.NONE,
        ),
        score=1.0,
        weight=weight,
    )


def _missing(
    requirement: QualificationItem,
    category: str,
    company_status: str,
    comment: str,
    weight: float,
) -> EvaluatedItem:
    return EvaluatedItem(
        bucket="missing",
        item=MatchItem(
            category=category,
            requirement=_requirement_text(requirement),
            company_status=company_status,
            is_matched=False,
            risk_level=RiskLevel.HIGH if requirement.is_mandatory else RiskLevel.MEDIUM,
            comment=comment,
        ),
        score=0.0,
        weight=weight,
    )


def _risk(
    requirement: QualificationItem,
    category: str,
    company_status: str,
    is_matched: bool,
    risk_level: RiskLevel,
    comment: str,
    weight: float,
    *,
    score: float,
) -> EvaluatedItem:
    return EvaluatedItem(
        bucket="risk",
        item=MatchItem(
            category=category,
            requirement=_requirement_text(requirement),
            company_status=company_status,
            is_matched=is_matched,
            risk_level=risk_level,
            comment=comment,
        ),
        score=score,
        weight=weight,
    )


def _normalize_category(requirement: QualificationItem) -> str:
    category = requirement.category.strip()
    if category in {"资质", "业绩", "人员", "财务", "其他"}:
        return category
    description = requirement.description
    if any(keyword in description for keyword in ("业绩", "合同", "案例")):
        return "业绩"
    if any(keyword in description for keyword in ("人员", "项目经理", "建造师", "工程师")):
        return "人员"
    if any(keyword in description for keyword in ("财务", "审计", "注册资本", "资产")):
        return "财务"
    if any(keyword in description for keyword in ("资质", "许可证", "认证")):
        return "资质"
    return "其他"


def _requirement_text(requirement: QualificationItem) -> str:
    return (requirement.original_text or requirement.description).strip()


def _requirement_weight(requirement: QualificationItem) -> float:
    return 1.0 if requirement.is_mandatory else 0.5


def _normalize(value: str | None) -> str:
    return _NORMALIZE_PATTERN.sub("", (value or "").lower())


def _record_matches_requirement(requirement: str, *fields: str | None) -> bool:
    normalized_requirement = _normalize(requirement)
    for field in fields:
        normalized_field = _normalize(field)
        if len(normalized_field) < 2:
            continue
        if normalized_field in normalized_requirement:
            return True
        ratio = SequenceMatcher(None, normalized_field, normalized_requirement).ratio()
        if len(normalized_field) >= 6 and ratio >= 0.55:
            return True
    return False


def _certificate_level_satisfies(requirement: str, actual_level: str | None) -> bool:
    required = _extract_level(requirement)
    if required is None:
        return True
    actual = _extract_level(actual_level or "")
    if actual is None:
        return False
    required_system, required_rank = required
    actual_system, actual_rank = actual
    return required_system == actual_system and actual_rank >= required_rank


def _extract_level(value: str) -> tuple[str, int] | None:
    normalized = value.replace("壹", "一").replace("贰", "二").replace("叁", "三")
    construction = {"特级": 4, "一级": 3, "二级": 2, "三级": 1}
    classification = {"甲级": 3, "乙级": 2, "丙级": 1}
    for name, rank in construction.items():
        if name in normalized:
            return "construction", rank
    for name, rank in classification.items():
        if name in normalized:
            return "classification", rank
    return None


def _performance_matches_requirement(
    requirement: str,
    performance: PerformanceRecord,
) -> bool:
    fields = (
        performance.related_qualification,
        performance.project_name,
        performance.description,
    )
    if _record_matches_requirement(requirement, *fields):
        return True
    overlap = _keyword_overlap(requirement, " ".join(value or "" for value in fields))
    return len(overlap) >= 2


def _only_generic_performance_requirement(requirement: str) -> bool:
    normalized = _normalize(requirement)
    stripped = normalized
    for term in _GENERIC_TERMS:
        stripped = stripped.replace(_normalize(term), "")
    stripped = re.sub(r"[0-9一二三四五六七八九十两年月日万元亿项个]+", "", stripped)
    return len(stripped) < 4


def _extract_specialties(requirement: str) -> set[str]:
    normalized_requirement = _normalize(requirement)
    return {
        specialty
        for specialty in _SPECIALTY_KEYWORDS
        if _normalize(specialty) in normalized_requirement
    }


def _specialty_satisfies(
    required_specialties: set[str],
    *record_fields: str | None,
) -> bool:
    if not required_specialties:
        return True
    normalized_record = _normalize(" ".join(value or "" for value in record_fields))
    return any(_normalize(specialty) in normalized_record for specialty in required_specialties)


def _keyword_overlap(left: str, right: str) -> list[str]:
    left_tokens = _tokens(left)
    normalized_right = _normalize(right)
    return [token for token in left_tokens if token in normalized_right]


def _tokens(value: str) -> list[str]:
    chunks = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]{2,}", value.lower())
    tokens: list[str] = []
    for chunk in chunks:
        normalized_chunk = _normalize(chunk)
        if normalized_chunk in {_normalize(term) for term in _GENERIC_TERMS}:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", normalized_chunk) and len(normalized_chunk) > 6:
            tokens.extend(
                normalized_chunk[index : index + 4]
                for index in range(len(normalized_chunk) - 3)
            )
        elif len(normalized_chunk) >= 2:
            tokens.append(normalized_chunk)
    return list(dict.fromkeys(tokens))


def _extract_amount(value: str) -> Decimal | None:
    amounts: list[Decimal] = []
    multipliers = {
        "元": Decimal(1),
        "万": Decimal(10000),
        "万元": Decimal(10000),
        "亿": Decimal(100000000),
        "亿元": Decimal(100000000),
    }
    for number, unit in _AMOUNT_PATTERN.findall(value):
        amounts.append(Decimal(number) * multipliers[unit])
    return max(amounts) if amounts else None


def _extract_count(value: str, *, unit: str) -> int | None:
    for number, actual_unit in _COUNT_PATTERN.findall(value):
        if actual_unit == unit:
            return _chinese_number_to_int(number)
    return None


def _extract_personnel_count(value: str) -> int | None:
    for number, unit in _COUNT_PATTERN.findall(value):
        if unit in {"名", "人", "位"}:
            return _chinese_number_to_int(number)
    return None


def _extract_recent_years(value: str) -> int | None:
    match = _RECENT_YEARS_PATTERN.search(value)
    return _chinese_number_to_int(match.group(1)) if match else None


def _extract_established_years(value: str) -> int | None:
    match = _ESTABLISHED_YEARS_PATTERN.search(value)
    return _chinese_number_to_int(match.group(1)) if match else None


def _chinese_number_to_int(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        return (digits.get(left, 1) * 10) + digits.get(right, 0)
    return digits.get(value, 1)


def _expires_soon(valid_to: date | None, days: int) -> bool:
    if valid_to is None:
        return False
    remaining = (valid_to - date.today()).days
    return 0 <= remaining <= days


def _full_years_since(start: date | None) -> int:
    if start is None:
        return 0
    today = date.today()
    return today.year - start.year - ((today.month, today.day) < (start.month, start.day))


def _years_ago(years: int) -> date:
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        # 2 月 29 日回退到目标年份的 2 月 28 日。
        return today.replace(year=today.year - years, day=28)
