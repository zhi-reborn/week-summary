import re
import unicodedata
from typing import Literal

from app.domain.facts import Fact, FactKind, Metric, SourceRef
from app.domain.quality import CoverageCell, QualityFinding, QualityLevel


class QualityService:
    def check_text(
        self,
        text: str,
        known_people: set[str],
        sources: list[SourceRef],
        metrics: list[Metric] | None = None,
    ) -> list[QualityFinding]:
        normalized_text = _normalize(text)
        source_text = "\n".join(_normalize(source.quote) for source in sources)
        metric_text = "\n".join(
            _normalize(f"{metric.label} {metric.value}{metric.unit or ''}")
            for metric in metrics or []
        )
        evidence = f"{source_text}\n{metric_text}"
        findings: list[QualityFinding] = []
        for name in _person_candidates(normalized_text):
            if name not in known_people:
                findings.append(
                    QualityFinding(
                        code="UNKNOWN_PERSON",
                        message=f"生成内容包含未识别人员：{name}",
                        token=name,
                    )
                )
        for token in _extract_markers(normalized_text):
            if token not in evidence:
                findings.append(
                    QualityFinding(
                        code="UNSOURCED_NUMBER",
                        message=f"数字、日期或版本缺少来源：{token}",
                        token=token,
                    )
                )
        return findings

    def build_coverage(
        self,
        *,
        person_ids: list[str],
        section_ids: list[str],
        facts: list[Fact],
        section_fact_ids: dict[str, set[str]],
        section_kinds: dict[str, set[FactKind]],
    ) -> list[CoverageCell]:
        cells: list[CoverageCell] = []
        for section_id in section_ids:
            allowed_kinds = section_kinds.get(section_id, set(FactKind))
            used_ids = section_fact_ids.get(section_id, set())
            for person_id in person_ids:
                relevant = [
                    fact
                    for fact in facts
                    if fact.kind in allowed_kinds
                    and any(source.person_id == person_id for source in fact.sources)
                ]
                referenced = [fact.id for fact in relevant if fact.id in used_ids]
                state: Literal["referenced", "unreferenced", "no_source_content"]
                if referenced:
                    state = "referenced"
                elif relevant:
                    state = "unreferenced"
                else:
                    state = "no_source_content"
                cells.append(
                    CoverageCell(
                        person_id=person_id,
                        section_id=section_id,
                        state=state,
                        fact_ids=[fact.id for fact in relevant],
                    )
                )
        return cells

    @staticmethod
    def level(
        findings: list[QualityFinding], *, required_section_empty: bool = False
    ) -> QualityLevel:
        if required_section_empty:
            return QualityLevel.FAILED
        codes = {finding.code for finding in findings}
        if codes & {"INVALID_STRUCTURE", "REQUIRED_SECTION_EMPTY"}:
            return QualityLevel.FAILED
        if codes & {"UNKNOWN_PERSON", "UNSOURCED_NUMBER", "UNREFERENCED_CONTENT"}:
            return QualityLevel.RISK
        if codes & {"LOW_CONFIDENCE", "POSSIBLE_DUPLICATE"}:
            return QualityLevel.CONFIRM
        return QualityLevel.PASS


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _extract_markers(text: str) -> list[str]:
    return [match.group(0) for match in _MARKER_PATTERN.finditer(text)]


def _person_candidates(text: str) -> list[str]:
    return [match.group(1) for match in _PERSON_PATTERN.finditer(text)]


_SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀羊甄曲封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍璩桑桂濮牛寿通边扈燕冀浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
_PERSON_PATTERN = re.compile(
    rf"(?<![\u3400-\u9fff])([{_SURNAMES}][\u3400-\u9fff]{{1,3}})(?=完成|负责|推进|交付|计划|上线)"
)
_MARKER_PATTERN = re.compile(
    r"(?:20\d{2}年\d{1,2}月\d{1,2}日|20\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?"
    r"|[¥￥]\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?(?:万元|元)|v\d+(?:\.\d+)+"
    r"|\d+(?:\.\d+)?%|\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
