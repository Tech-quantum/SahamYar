package com.techquantum.sahamyar.ui.stockdetail

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.techquantum.sahamyar.data.repository.StockOverviewData
import com.techquantum.sahamyar.data.remote.model.StockAnalysisResponse

private val DetailBackground = Color(0xFF17191D)
private val DetailSurface = Color(0xFF252930)
private val DetailOrange = Color(0xFFFF8A00)
private val DetailText = Color(0xFFF5F5F5)
private val DetailMuted = Color(0xFFA6ABB3)
private val DetailGreen = Color(0xFF16C784)
private val DetailRed = Color(0xFFEA5455)

@Composable
fun StockDetailScreen(
    insCode: String,
    instrumentCategory: String? = null,
    instrumentCategoryLabel: String? = null,
    modifier: Modifier = Modifier,
    onBack: () -> Unit
) {
    val vm: StockDetailViewModel = viewModel()
    val state by vm.state.collectAsState()

    LaunchedEffect(insCode, instrumentCategory, instrumentCategoryLabel) {
        vm.loadStock(insCode, instrumentCategory, instrumentCategoryLabel)
    }

    Column(
        modifier = modifier
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp, vertical = 14.dp)
    ) {
        TextButton(onClick = onBack) {
            Text("→ بازگشت به بازار", color = DetailOrange)
        }

        when {
            state.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxWidth().padding(top = 90.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = DetailOrange)
                }
            }

            state.error != null -> {
                DetailCard {
                    Text("دریافت اطلاعات ناموفق بود", color = DetailText,
                        fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    Text(state.error ?: "خطای نامشخص", color = DetailMuted)
                    Spacer(Modifier.height(12.dp))
                    Button(
                        onClick = {
                            vm.loadStock(
                                insCode,
                                instrumentCategory,
                                instrumentCategoryLabel,
                                forceRefresh = true
                            )
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = DetailOrange)
                    ) {
                        Text("تلاش مجدد", color = Color.Black)
                    }
                }
            }

            state.data != null -> StockOverviewContent(state.data!!)
        }
    }
}

@Composable
private fun StockOverviewContent(data: StockOverviewData) {
    val detail = data.detail.item
    val price = data.prices?.item
    val analysis = data.analysis
    val historyItems = data.history?.items.orEmpty()

    val category = data.instrumentCategory
        ?: detail?.instrument_category ?: "OTHER"
    val categoryLabel = data.instrumentCategoryLabel
        ?: detail?.instrument_category_label ?: "سایر"
    val supportsEquityAnalysis =
        category == "COMMON_STOCK" || category == "RIGHTS"

    val change = if (
        price?.last_price != null && price.yesterday_price != null
    ) price.last_price - price.yesterday_price else null

    val changePercent = if (
        change != null && price?.yesterday_price != null && price.yesterday_price != 0L
    ) change.toDouble() * 100.0 / price.yesterday_price else null

    Column {
        Text(
            detail?.symbol ?: "جزئیات ابزار مالی",
            color = DetailOrange,
            fontSize = 27.sp,
            fontWeight = FontWeight.Bold
        )
        Spacer(Modifier.height(5.dp))
        Text(detail?.name ?: "نام ابزار نامشخص", color = DetailText, fontSize = 15.sp)
        Spacer(Modifier.height(5.dp))
        Text(
            "${detail?.market ?: "بازار نامشخص"}  •  کد: ${detail?.ins_code ?: data.detail.ins_code ?: "—"}",
            color = DetailMuted,
            fontSize = 11.sp
        )
        Spacer(Modifier.height(8.dp))
        Surface(
            color = DetailSurface,
            shape = RoundedCornerShape(8.dp)
        ) {
            Text(
                categoryLabel,
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                color = DetailOrange,
                fontSize = 11.sp
            )
        }

        if (supportsEquityAnalysis) {
            Spacer(Modifier.height(20.dp))
            DetailCard {
                Text("آخرین وضعیت قیمت", color = DetailMuted, fontSize = 13.sp)
                Spacer(Modifier.height(10.dp))
                Text(
                    price?.last_price?.let { formatAmount(it) } ?: "داده قیمت در دسترس نیست",
                    color = DetailText,
                    fontSize = 25.sp,
                    fontWeight = FontWeight.Bold
                )
                Text("ریال", color = DetailMuted, fontSize = 11.sp)
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val movementColor = when {
                        change == null -> DetailMuted
                        change > 0 -> DetailGreen
                        change < 0 -> DetailRed
                        else -> DetailMuted
                    }
                    Text(
                        change?.let { "${formatAmount(it)} ریال" } ?: "—",
                        color = movementColor,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.width(12.dp))
                    Text(
                        changePercent?.let { "%+.2f%%".format(it) } ?: "—",
                        color = movementColor,
                        fontWeight = FontWeight.SemiBold
                    )
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "قیمت پایانی: ${price?.closing_price?.let { formatAmount(it) } ?: "—"} ریال",
                    color = DetailMuted,
                    fontSize = 12.sp
                )
                Text(
                    "معادل آخرین قیمت: ${price?.last_price?.div(10)?.let { formatAmount(it) } ?: "—"} تومان",
                    color = DetailMuted,
                    fontSize = 12.sp
                )
            }

            Spacer(Modifier.height(16.dp))
            if (historyItems.isNotEmpty()) {
                StockPriceChart(historyItems)
            } else {
                DetailCard {
                    Text("تاریخچه قیمت برای نمودار در دسترس نیست.", color = DetailMuted)
                }
            }

            Spacer(Modifier.height(16.dp))
            DetailSectionTitle("اطلاعات معاملات")
            DetailCard {
                DetailValueRow("اولین قیمت", price?.first_price)
                DetailValueRow("کمترین قیمت روز", price?.min_price)
                DetailValueRow("بیشترین قیمت روز", price?.max_price)
                DetailValueRow("قیمت دیروز", price?.yesterday_price)
                DetailValueRow("تعداد معاملات", price?.trade_count, "معامله")
                DetailValueRow("حجم معاملات", price?.volume, "سهم")
                DetailValueRow("ارزش معاملات", price?.value, "ریال")
            }

            Spacer(Modifier.height(16.dp))
            DetailSectionTitle("ارزیابی هوشمند")
            if (analysis != null) {
                AnalysisSummaryCard(analysis)
            } else {
                DetailCard {
                    Text(
                        "داده کافی برای ارزیابی هوشمند این نماد دریافت نشد.",
                        color = DetailMuted
                    )
                }
            }

            if (analysis != null) {
                Spacer(Modifier.height(16.dp))
                DetailSectionTitle("تحلیل تکنیکال")
                val indicators = analysis.indicators

                DetailCard {
                    Text("میانگین‌های متحرک", color = DetailText, fontWeight = FontWeight.Bold)
                    DetailIndicatorRow("SMA 20", indicators?.sma?.get("20"))
                    DetailIndicatorRow("SMA 50", indicators?.sma?.get("50"))
                    DetailIndicatorRow("SMA 200", indicators?.sma?.get("200"))
                    DetailIndicatorRow("EMA 12", indicators?.ema?.get("12"))
                    DetailIndicatorRow("EMA 26", indicators?.ema?.get("26"))
                }

                Spacer(Modifier.height(8.dp))
                DetailCard {
                    Text("شاخص قدرت نسبی (RSI)", color = DetailText, fontWeight = FontWeight.Bold)
                    Text(
                        indicators?.rsi?.get("14")?.let {
                            "%.2f".format(java.util.Locale.US, it)
                        } ?: "داده کافی نیست",
                        color = DetailOrange,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text("دوره ۱۴", color = DetailMuted, fontSize = 11.sp)
                }

                Spacer(Modifier.height(8.dp))
                DetailCard {
                    Text("مکدی (MACD)", color = DetailText, fontWeight = FontWeight.Bold)
                    DetailIndicatorRow("خط MACD", indicators?.macd?.line)
                    DetailIndicatorRow("خط سیگنال", indicators?.macd?.signal)
                    DetailIndicatorRow("هیستوگرام", indicators?.macd?.histogram)
                }
                Text(
                    "تعداد روزهای مبنای تحلیل: ${analysis.count}",
                    color = DetailMuted,
                    fontSize = 11.sp
                )
            }

            Spacer(Modifier.height(16.dp))
            DetailSectionTitle("مشخصات شرکت")
            DetailCard {
                DetailValueRow("گروه صنعت", null, detail?.sector ?: "—")
                DetailValueRow("تعداد سهام", detail?.shares_count, "سهم")
                DetailValueRow("میانگین حجم معاملات ۵ روزه", detail?.average_volume, "سهم")
                DetailDecimalRow("EPS ثبت‌شده (TSETMC)", detail?.fundamentals?.eps_actual)
                DetailDecimalRow("EPS برآوردی (TSETMC)", detail?.fundamentals?.eps_estimated)
                DetailDecimalRow("P/E صنعت (TSETMC)", detail?.fundamentals?.sector_pe)
                DetailValueRow("کمترین قیمت هفتگی", detail?.min_week)
                DetailValueRow("بیشترین قیمت هفتگی", detail?.max_week)
                DetailValueRow("کمترین قیمت سالانه", detail?.min_year)
                DetailValueRow("بیشترین قیمت سالانه", detail?.max_year)
            }

            Spacer(Modifier.height(16.dp))
            DetailSectionTitle("تاریخچه قیمت")
            if (historyItems.isEmpty()) {
                DetailCard {
                    Text("تاریخچه‌ای برای نمایش موجود نیست.", color = DetailMuted)
                }
            } else {
                historyItems.sortedBy { it.date }.takeLast(30).asReversed().forEach { item ->
                    DetailCard {
                        Text(formatJalaliDate(item.date), color = DetailMuted, fontSize = 11.sp)
                        Spacer(Modifier.height(6.dp))
                        DetailValueRow("قیمت پایانی", item.closing_price)
                        DetailValueRow("آخرین قیمت", item.last_price)
                        DetailValueRow("حجم", item.volume, "سهم")
                    }
                    Spacer(Modifier.height(8.dp))
                }
            }
        } else {
            Spacer(Modifier.height(20.dp))
            DetailCard {
                Text("تحلیل اختصاصی $categoryLabel", color = DetailText, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                val message = when (category) {
                    "FUND" ->
                        "برای تحلیل صندوق، داده‌های NAV، قیمت ابطال و صدور، فاصله قیمت بازار از NAV و ترکیب دارایی‌ها لازم است. این داده‌ها هنوز به منبع معتبر متصل نشده‌اند."
                    "DEBT" ->
                        "برای تحلیل اوراق بدهی، نرخ بازده مؤثر، بازده تا سررسید، تاریخ سررسید و شرایط پرداخت لازم است. این داده‌ها هنوز به منبع معتبر متصل نشده‌اند."
                    else ->
                        "نوع این ابزار در گروه سایر قرار گرفته است. تا زمان شناسایی دقیق نوع ابزار و اتصال داده‌های تخصصی، تحلیل و پیشنهاد معاملاتی ارائه نمی‌شود."
                }
                Text(message, color = DetailMuted, fontSize = 13.sp)
            }
        }

        Spacer(Modifier.height(20.dp))
    }
}

@Composable
private fun DetailIndicatorRow(label: String, value: Double?) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, color = DetailMuted, fontSize = 12.sp)
        Text(
            value?.let { "%.4f".format(java.util.Locale.US, it) } ?: "داده کافی نیست",
            color = DetailText,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun DetailDecimalRow(label: String, value: Double?) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = DetailMuted, fontSize = 12.sp)
        Text(
            value?.let { "%.2f".format(java.util.Locale.US, it) } ?: "—",
            color = DetailText,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun DetailSectionTitle(title: String) {
    Text(title, color = DetailText, fontSize = 17.sp, fontWeight = FontWeight.Bold)
    Spacer(Modifier.height(10.dp))
}

@Composable
private fun DetailCard(content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DetailSurface)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            content = content
        )
    }
}

@Composable
private fun DetailValueRow(
    label: String,
    value: Long?,
    suffix: String = "ریال"
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = DetailMuted, fontSize = 12.sp)
        Text(
            value?.let { "${formatAmount(it)} $suffix" } ?: "—",
            color = DetailText,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

private fun formatJalaliDate(date: Long?): String {
    if (date == null) return "تاریخ نامشخص"

    val value = date.toString()
    if (value.length != 8) return "تاریخ نامعتبر"

    val year = value.substring(0, 4).toIntOrNull() ?: return "تاریخ نامعتبر"
    val month = value.substring(4, 6).toIntOrNull() ?: return "تاریخ نامعتبر"
    val day = value.substring(6, 8).toIntOrNull() ?: return "تاریخ نامعتبر"

    if (year !in 1601..9999 || month !in 1..12) return "تاریخ نامعتبر"

    val isLeapYear = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
    val monthLengths = intArrayOf(31, if (isLeapYear) 29 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if (day !in 1..monthLengths[month - 1]) return "تاریخ نامعتبر"

    val gDaysInMonth = intArrayOf(31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    val jDaysInMonth = intArrayOf(31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)

    var gy = year
    var gm = month
    var gd = day

    gy -= if (gm > 2) 1600 else 1601
    gm -= 1
    gd -= 1

    var gDayNo = 365 * gy + (gy + 3) / 4 - (gy + 99) / 100 + (gy + 399) / 400
    for (i in 0 until gm) gDayNo += gDaysInMonth[i]
    if (gm > 1 && (year % 4 == 0 && year % 100 != 0 || year % 400 == 0)) gDayNo++
    gDayNo += gd

    var jDayNo = gDayNo - 79
    val jNp = jDayNo / 12053
    jDayNo %= 12053

    var jy = 979 + 33 * jNp + 4 * (jDayNo / 1461)
    jDayNo %= 1461

    if (jDayNo >= 366) {
        jy += (jDayNo - 1) / 365
        jDayNo = (jDayNo - 1) % 365
    }

    var jm = 0
    while (jm < 11 && jDayNo >= jDaysInMonth[jm]) {
        jDayNo -= jDaysInMonth[jm]
        jm++
    }
    val jd = jDayNo + 1

    return "%04d/%02d/%02d".format(java.util.Locale.US, jy, jm + 1, jd)
}

private fun formatAmount(value: Long): String = "%,d".format(value)


@Composable
private fun AnalysisSummaryCard(analysis: StockAnalysisResponse) {
    val recommendation = analysis.recommendation
    val layers = analysis.layers

    DetailCard {
        Text(
            "وضعیت پیشنهاد",
            color = DetailMuted,
            fontSize = 12.sp
        )
        Spacer(Modifier.height(6.dp))
        Text(
            recommendation?.action?.let { recommendationLabel(it) } ?: "اطلاعات پیشنهاد موجود نیست",
            color = DetailOrange,
            fontSize = 19.sp,
            fontWeight = FontWeight.Bold
        )
        recommendation?.confidence?.let {
            Text(
                "اطمینان مدل: %.0f%%".format(java.util.Locale.US, it * 100.0),
                color = DetailMuted,
                fontSize = 12.sp
            )
        }
        recommendation?.reason?.takeIf { it.isNotBlank() }?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = DetailText, fontSize = 12.sp)
        }

        Spacer(Modifier.height(14.dp))
        HorizontalDivider(color = DetailMuted.copy(alpha = 0.25f))
        Spacer(Modifier.height(10.dp))

        Text("وضعیت لایه‌های تحلیل", color = DetailText, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))

        AnalysisLayerRow("تحلیل تکنیکال سهام", layers?.stock?.technical?.status)
        AnalysisLayerRow("تحلیل بنیادی سهام", layers?.stock?.fundamental?.status)
        AnalysisLayerRow("اقتصاد ایران", layers?.iran_economy?.status)
        AnalysisLayerRow("تحولات سیاسی و ریسک‌ها", layers?.geopolitical?.status)
        AnalysisLayerRow("بازارهای جهانی", layers?.global_markets?.status)

        Spacer(Modifier.height(10.dp))
        Text(
            when (analysis.analysis_status) {
                "AVAILABLE" -> "تحلیل با داده‌های در دسترس تکمیل شده است."
                "PARTIAL" -> "تحلیل ناقص است؛ برخی منابع هنوز متصل نیستند."
                "INSUFFICIENT_DATA" -> "داده کافی برای تحلیل معتبر وجود ندارد."
                else -> "وضعیت تکمیل تحلیل مشخص نیست."
            },
            color = DetailMuted,
            fontSize = 11.sp
        )
    }
}

@Composable
private fun AnalysisLayerRow(label: String, status: String?) {
    val (description, color) = when (status) {
        "AVAILABLE" -> "داده موجود" to DetailGreen
        "PARTIAL" -> "داده ناقص" to DetailOrange
        "STALE" -> "داده قدیمی" to DetailRed
        "INSUFFICIENT_DATA" -> "داده ناکافی" to DetailOrange
        "UNAVAILABLE" -> "منبع متصل نیست" to DetailMuted
        else -> "نامشخص" to DetailMuted
    }

    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = DetailText, fontSize = 12.sp)
        Text(description, color = color, fontSize = 11.sp, fontWeight = FontWeight.Medium)
    }
}

private fun recommendationLabel(action: String): String = when (action) {
    "BUY" -> "پیشنهاد تحلیلی: خرید"
    "SELL" -> "پیشنهاد تحلیلی: فروش"
    "HOLD" -> "پیشنهاد تحلیلی: نگهداری"
    "WAIT" -> "پیشنهاد تحلیلی: انتظار"
    "INSUFFICIENT_DATA" -> "داده کافی برای پیشنهاد وجود ندارد"
    else -> "پیشنهاد نامشخص"
}
