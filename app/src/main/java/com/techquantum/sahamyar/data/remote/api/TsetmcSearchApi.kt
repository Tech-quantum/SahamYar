package com.techquantum.sahamyar.data.remote.api

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName
import com.techquantum.sahamyar.data.remote.model.StockSearchItem
import com.techquantum.sahamyar.data.remote.model.StockSearchResponse
import okhttp3.OkHttpClient
import okhttp3.Interceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import java.time.Instant
import java.util.concurrent.TimeUnit

private data class TsetmcSearchPayload(
    @SerializedName("instrumentSearch")
    val instruments: List<TsetmcInstrumentDto?>?
)

private data class TsetmcInstrumentDto(
    @SerializedName("insCode") val insCode: JsonElement?,
    @SerializedName("lVal18AFC") val symbol: String?,
    @SerializedName("lVal30") val name: String?,
    @SerializedName("cIsin") val isin: String?,
    @SerializedName("flow") val flow: JsonElement?,
    @SerializedName("flowTitle") val flowTitle: String?,
    @SerializedName("cgrValCot") val instrumentType: JsonElement?
)

private interface TsetmcSearchService {
    @GET("Instrument/GetInstrumentSearch/{query}")
    suspend fun search(
        @Path("query") query: String
    ): Response<TsetmcSearchPayload>
}

object TsetmcSearchApi {

    private const val BASE_URL = "https://cdn.tsetmc.com/api/"

    private val service: TsetmcSearchService by lazy {
        val headersInterceptor = Interceptor { chain ->
            val request = chain.request().newBuilder()
                .header(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
                )
                .header("Accept", "application/json, text/plain, */*")
                .header("Referer", "https://www.tsetmc.com/")
                .header("Origin", "https://www.tsetmc.com")
                .build()
            chain.proceed(request)
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(headersInterceptor)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .build()

        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TsetmcSearchService::class.java)
    }

    suspend fun searchStocks(query: String): StockSearchResponse {
        val cleanQuery = query.trim()
        require(cleanQuery.length >= 2) {
            "عبارت جستجو باید حداقل دو کاراکتر باشد."
        }

        val normalizedQuery = cleanQuery
            .replace("ی", "ي")
            .replace("ک", "ك")

        val response = service.search(normalizedQuery)

        if (!response.isSuccessful) {
            throw IllegalStateException("خطا در دریافت اطلاعات TSETMC: ${response.code()}")
        }

        val payload = response.body()
            ?: throw IllegalStateException("پاسخ TSETMC خالی است.")

        val rows = payload.instruments
            ?: throw IllegalStateException("ساختار پاسخ جست‌وجوی TSETMC معتبر نیست.")

        val items = rows.filterNotNull().map { row ->
            val instrumentType = row.instrumentType.stringValue()
                ?.trim()
                ?.uppercase()
                ?.takeIf { it.isNotEmpty() }

            val (category, categoryLabel) = TsetmcInstrumentClassifier.classify(
                row.name.orEmpty(),
                instrumentType
            )

            StockSearchItem(
                ins_code = row.insCode.stringValue(),
                symbol = row.symbol,
                name = row.name,
                isin = row.isin,
                market_flow = row.flow.stringValue()?.toIntOrNull(),
                market = row.flowTitle,
                instrument_type = instrumentType,
                instrument_category = category,
                instrument_category_label = categoryLabel
            )
        }

        return StockSearchResponse(
            source = "TSETMC",
            query = cleanQuery,
            count = items.size,
            items = items,
            retrieved_at = Instant.now().toString()
        )
    }

    private fun JsonElement?.stringValue(): String? {
        if (this == null || isJsonNull) return null
        return runCatching { asString }.getOrNull()
    }
}
