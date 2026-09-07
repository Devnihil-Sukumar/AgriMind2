"""
==========================================================================
AgriMind

Evidence Aggregator

Module 13U — Evidence Ranking

Responsibilities
----------------
1. Collect evidence from specialist agents.
2. Measure evidence quality.
3. Measure decision relevance.
4. Incorporate specialist confidence.
5. Detect supporting and contradicting evidence.
6. Calculate weighted evidence scores.
7. Rank evidence sources.
8. Preserve raw evidence for explainability.

Author : AgriMind Team
==========================================================================
"""


class EvidenceAggregator:

    """
    Aggregates and ranks heterogeneous specialist evidence.
    """

    ####################################################################
    # Source Priorities
    ####################################################################

    SOURCE_PRIORITIES = {

        "SatelliteAgent": 0.95,

        "WeatherAgent": 0.90,

        "SoilAgent": 0.85,

        "MarketAgent": 0.80,

        "HistoricalAgent": 0.65

    }

    ####################################################################
    # Evidence Type Priorities
    ####################################################################

    EVIDENCE_TYPES = {

        "risk": 1.00,

        "opportunity": 0.85,

        "analysis": 0.90,

        "summary": 0.90

    }

    ####################################################################
    # Convert Confidence
    ####################################################################

    def _confidence(

        self,

        value

    ):

        try:

            value = float(

                value

            )

        except (

            TypeError,

            ValueError

        ):

            return 0.0

        if value > 1:

            value /= 100

        return max(

            0.0,

            min(

                value,

                1.0

            )

        )

    ####################################################################
    # Text Normalization
    ####################################################################

    def _text(

        self,

        value

    ):

        if value is None:

            return ""

        return str(

            value

        ).strip()

    ####################################################################
    # Decision Relevance
    ####################################################################

    def _decision_relevance(

        self,

        source,

        executive_decision,

        reasoning

    ):

        decision_text = (

            self._text(

                executive_decision.get(

                    "decision",

                    executive_decision.get(

                        "executive_decision",

                        ""

                    )

                )

            )

            + " "

            +

            self._text(

                executive_decision.get(

                    "recommendation",

                    ""

                )

            )

        ).lower()

        source_keywords = {

            "WeatherAgent": [

                "weather",

                "rain",

                "rainfall",

                "temperature",

                "humidity",

                "wind",

                "irrigation",

                "water"

            ],

            "SoilAgent": [

                "soil",

                "nitrogen",

                "organic",

                "fertilizer",

                "nutrient",

                "pH",

                "texture"

            ],

            "SatelliteAgent": [

                "satellite",

                "vegetation",

                "ndvi",

                "ndwi",

                "water stress",

                "irrigation",

                "crop health",

                "disease"

            ],

            "MarketAgent": [

                "market",

                "price",

                "selling",

                "sell",

                "profit",

                "harvest"

            ],

            "HistoricalAgent": [

                "historical",

                "previous",

                "season",

                "past",

                "recurring",

                "history"

            ]

        }

        keywords = source_keywords.get(

            source,

            []

        )

        if not keywords:

            return 0.50

        matches = sum(

            1

            for keyword in keywords

            if keyword.lower() in decision_text

        )

        return min(

            1.0,

            0.40

            +

            (

                matches

                /

                max(

                    len(keywords),

                    1

                )

            )

            * 0.60

        )

    ####################################################################
    # Source Reliability
    ####################################################################

    def _source_reliability(

        self,

        source,

        output

    ):

        base = self.SOURCE_PRIORITIES.get(

            source,

            0.60

        )

        metadata = output.get(

            "metadata",

            {}

        )

        ############################################################
        # Penalize missing evidence
        ############################################################

        if output.get(

            "status"

        ) != "completed":

            return 0.0

        ############################################################
        # Historical availability
        ############################################################

        if source == "HistoricalAgent":

            available = metadata.get(

                "historical_available"

            )

            if available is False:

                return 0.30

        ############################################################
        # Soil provenance
        ############################################################

        if source == "SoilAgent":

            live_source = metadata.get(

                "live_source"

            )

            if live_source is False:

                return 0.75

        ############################################################
        # Satellite quality
        ############################################################

        if source == "SatelliteAgent":

            cloud_cover = (

                metadata.get(

                    "cloud_cover"

                )

            )

            if cloud_cover is not None:

                try:

                    cloud_cover = float(

                        cloud_cover

                    )

                    if cloud_cover >= 50:

                        base *= 0.65

                    elif cloud_cover >= 30:

                        base *= 0.85

                except (

                    TypeError,

                    ValueError

                ):

                    pass

        ############################################################
        # Market provenance
        ############################################################

        if source == "MarketAgent":

            source_type = self._text(

                metadata.get(

                    "source",

                    ""

                )

            ).lower()

            if "synthetic" in source_type:

                base *= 0.75

        return max(

            0.0,

            min(

                base,

                1.0

            )

        )

    ####################################################################
    # Extract Findings
    ####################################################################

    def _extract_findings(

        self,

        source,

        output,

        executive_decision,

        reasoning

    ):

        findings = []

        ############################################################
        # Analysis
        ############################################################

        analysis = self._text(

            output.get(

                "analysis",

                ""

            )

        )

        if analysis:

            findings.append(

                {

                    "source":

                        source,

                    "type":

                        "analysis",

                    "finding":

                        analysis

                }

            )

        ############################################################
        # Summary
        ############################################################

        summary = self._text(

            output.get(

                "summary",

                ""

            )

        )

        if summary and summary != analysis:

            findings.append(

                {

                    "source":

                        source,

                    "type":

                        "summary",

                    "finding":

                        summary

                }

            )

        ############################################################
        # Risks
        ############################################################

        for risk in output.get(

            "risks",

            []

        ):

            if self._text(

                risk

            ):

                findings.append(

                    {

                        "source":

                            source,

                        "type":

                            "risk",

                        "finding":

                            self._text(

                                risk

                            )

                    }

                )

        ############################################################
        # Opportunities
        ############################################################

        for opportunity in output.get(

            "opportunities",

            []

        ):

            if self._text(

                opportunity

            ):

                findings.append(

                    {

                        "source":

                            source,

                        "type":

                            "opportunity",

                        "finding":

                            self._text(

                                opportunity

                            )

                    }

                )

        return findings

    ####################################################################
    # Calculate Score
    ####################################################################

    def _score(

        self,

        source,

        output,

        finding,

        executive_decision,

        reasoning

    ):

        confidence = self._confidence(

            output.get(

                "confidence",

                0

            )

        )

        reliability = self._source_reliability(

            source,

            output

        )

        relevance = self._decision_relevance(

            source,

            executive_decision,

            reasoning

        )

        evidence_type_weight = self.EVIDENCE_TYPES.get(

            finding["type"],

            0.70

        )

        ############################################################
        # Risk evidence gets slightly stronger influence because
        # it often drives intervention decisions.
        ############################################################

        score = (

            0.35 * confidence

            +

            0.30 * reliability

            +

            0.25 * relevance

            +

            0.10 * evidence_type_weight

        )

        return round(

            max(

                0.0,

                min(

                    score,

                    1.0

                )

            ),

            4

        )

    ####################################################################
    # Importance Label
    ####################################################################

    def _importance(

        self,

        score

    ):

        if score >= 0.90:

            return "Critical"

        if score >= 0.80:

            return "High"

        if score >= 0.65:

            return "Moderate"

        if score >= 0.50:

            return "Low"

        return "Very Low"

    ####################################################################
    # Aggregate
    ####################################################################

    def aggregate(

        self,

        specialists,

        reasoning,

        executive_decision

    ):

        ranked = []

        ############################################################
        # Specialists
        ############################################################

        for source, output in specialists.items():

            findings = self._extract_findings(

                source,

                output,

                executive_decision,

                reasoning

            )

            for finding in findings:

                score = self._score(

                    source,

                    output,

                    finding,

                    executive_decision,

                    reasoning

                )

                ranked.append(

                    {

                        "source":

                            source,

                        "type":

                            finding["type"],

                        "finding":

                            finding["finding"],

                        "confidence":

                            round(

                                self._confidence(

                                    output.get(

                                        "confidence",

                                        0

                                    )

                                ),

                                4

                            ),

                        "reliability":

                            round(

                                self._source_reliability(

                                    source,

                                    output

                                ),

                                4

                            ),

                        "decision_relevance":

                            round(

                                self._decision_relevance(

                                    source,

                                    executive_decision,

                                    reasoning

                                ),

                                4

                            ),

                        "evidence_score":

                            score,

                        "importance":

                            self._importance(

                                score

                            )

                    }

                )

        ############################################################
        # Highest evidence first
        ############################################################

        ranked.sort(

            key=lambda item:

                item["evidence_score"],

            reverse=True

        )

        ############################################################
        # Assign ranks
        ############################################################

        for index, item in enumerate(

            ranked,

            start=1

        ):

            item["rank"] = index

        ############################################################
        # Source Summary
        ############################################################

        source_summary = {}

        for item in ranked:

            source = item["source"]

            source_summary.setdefault(

                source,

                {

                    "evidence_score":

                        0.0,

                    "finding_count":

                        0,

                    "highest_importance":

                        "Very Low"

                }

            )

            source_summary[source][

                "evidence_score"

            ] = max(

                source_summary[source][

                    "evidence_score"

                ],

                item["evidence_score"]

            )

            source_summary[source][

                "finding_count"

            ] += 1

        ############################################################
        # Normalize source summary
        ############################################################

        for source, summary in source_summary.items():

            summary["evidence_score"] = round(

                summary["evidence_score"],

                4

            )

            summary["highest_importance"] = self._importance(

                summary["evidence_score"]

            )

        ############################################################

        return {

            "ranked_evidence":

                ranked,

            "source_summary":

                source_summary,

            "total_findings":

                len(

                    ranked

                ),

            "top_evidence":

                ranked[:5]

        }


##########################################################################

evidence_aggregator = EvidenceAggregator()