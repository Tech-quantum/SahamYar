package com.techquantum.sahamyar.data.remote.api

object TsetmcInstrumentClassifier {

    fun classify(
        originalName: String,
        instrumentType: String?
    ): Pair<String, String> {
        val name = originalName
            .replace('\u200c', ' ')
            .replace("\u200f", "")
            .replace("\u200e", "")
            .replace('\u00a0', ' ')
            .trim()

        val isRights = Regex("^(?:ح\\s*\\.?\\s*|حق\\s*تقدم)")
            .containsMatchIn(name)

        return when {
            isRights -> "RIGHTS" to "حق‌تقدم"
            instrumentType?.uppercase() in setOf("N1", "N2", "Z1") ->
                "COMMON_STOCK" to "سهام"
            instrumentType?.uppercase() in setOf("H1", "51") ->
                "FUND" to "صندوق"
            instrumentType == "17" ->
                "DEBT" to "اوراق بدهی"
            else -> "OTHER" to "سایر"
        }
    }
}
