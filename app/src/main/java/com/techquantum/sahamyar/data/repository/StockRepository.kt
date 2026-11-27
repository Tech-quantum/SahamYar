package com.techquantum.sahamyar.data.repository

import com.techquantum.sahamyar.data.remote.api.TsetmcAnalysisMapper
import com.techquantum.sahamyar.data.remote.api.TsetmcMarketApi
import com.techquantum.sahamyar.data.remote.api.TsetmcSearchApi
import com.techquantum.sahamyar.data.remote.api.TsetmcStockMapper
import com.techquantum.sahamyar.data.remote.model.StockAnalysisResponse
import com.techquantum.sahamyar.data.remote.model.StockDetailResponse
import com.techquantum.sahamyar.data.remote.model.StockHistoryResponse
import com.techquantum.sahamyar.data.remote.model.StockPriceResponse
import com.techquantum.sahamyar.data.remote.model.StockSearchResponse
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

data class StockOverviewData(
    val detail: StockDetailResponse,
    val analysis: StockAnalysisResponse?,
    val priceResult: RequestResult<StockPriceResponse>,
    val historyResult: RequestResult<StockHistoryResponse>,
    val instrumentCategory: String?,
    val instrumentCategoryLabel: String?
) {
    val prices: StockPriceResponse? get() = priceResult.data
    val history: StockHistoryResponse? get() = historyResult.data
}

class StockRepository {

    suspend fun searchStocks(query: String): Result<StockSearchResponse> {
        if (query.trim().length < 2) {
            return Result.failure(
                IllegalArgumentException("عبارت جستجو باید حداقل دو کاراکتر باشد.")
            )
        }

        return try {
            Result.success(TsetmcSearchApi.searchStocks(query.trim()))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getStockOverview(
        insCode: String,
        instrumentCategoryOverride: String? = null,
        instrumentCategoryLabelOverride: String? = null,
        historyCount: Int = 365,
        analysisCount: Int = 365
    ): Result<StockOverviewData> {
        if (insCode.isBlank()) {
            return Result.failure(
                IllegalArgumentException("کد نماد معتبر نیست.")
            )
        }

        if (historyCount !in 1..365 || analysisCount !in 1..365) {
            return Result.failure(
                IllegalArgumentException(
                    "تعداد روزهای تاریخچه و تحلیل باید بین ۱ تا ۳۶۵ باشد."
                )
            )
        }

        return try {
            val overview = coroutineScope {
                val rawDetail = TsetmcMarketApi.instrumentInfo(insCode)
                val detail = TsetmcStockMapper.detail(insCode, rawDetail)

                val category = instrumentCategoryOverride
                    ?: detail.item?.instrument_category
                val categoryLabel = instrumentCategoryLabelOverride
                    ?: detail.item?.instrument_category_label

                val supportsStockTechnical =
                    category == "COMMON_STOCK" || category == "RIGHTS"

                if (!supportsStockTechnical) {
                    StockOverviewData(
                        detail = detail,
                        analysis = null,
                        priceResult = RequestResult(null, RequestStatus.NOT_SUPPORTED),
                        historyResult = RequestResult(null, RequestStatus.NOT_SUPPORTED),
                        instrumentCategory = category,
                        instrumentCategoryLabel = categoryLabel
                    )
                } else {
                    val requestedHistoryCount = maxOf(historyCount, analysisCount)

                    val pricesDeferred = async {
                        executeOptionalRequest {
                            TsetmcStockMapper.price(
                                insCode,
                                TsetmcMarketApi.closingPriceInfo(insCode)
                            )
                        }
                    }

                    val historyDeferred = async {
                        executeOptionalRequest {
                            TsetmcStockMapper.history(
                                insCode,
                                TsetmcMarketApi.dailyPrices(insCode, requestedHistoryCount),
                                requestedHistoryCount
                            )
                        }
                    }

                    val priceResult = pricesDeferred.await()
                    var historyResult = historyDeferred.await()

                    val fullHistory = historyResult.data
                    if (fullHistory != null &&
                        fullHistory.items.none { (it.closing_price ?: 0L) > 0L }
                    ) {
                        historyResult = historyResult.copy(
                            status = RequestStatus.INSUFFICIENT_DATA,
                            message = "تاریخچه دریافت شد، اما قیمت پایانی معتبر ندارد."
                        )
                    }

                    val displayHistory = fullHistory?.let { result ->
                        val items = result.items.takeLast(historyCount)
                        result.copy(count = items.size, items = items)
                    }

                    val analysis = fullHistory?.let {
                        TsetmcAnalysisMapper.analyze(it, analysisCount)
                    }

                    StockOverviewData(
                        detail = detail,
                        analysis = analysis,
                        priceResult = priceResult,
                        historyResult = historyResult.copy(
                            data = displayHistory
                        ),
                        instrumentCategory = category,
                        instrumentCategoryLabel = categoryLabel
                    )
                }
            }

            Result.success(overview)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
    }


}
