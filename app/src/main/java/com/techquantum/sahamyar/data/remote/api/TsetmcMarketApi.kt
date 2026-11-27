package com.techquantum.sahamyar.data.remote.api

import com.google.gson.JsonObject
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

private interface TsetmcMarketService {
    @GET("Instrument/GetInstrumentInfo/{insCode}")
    suspend fun getInstrumentInfo(
        @Path("insCode") insCode: String
    ): Response<JsonObject>

    @GET("ClosingPrice/GetClosingPriceInfo/{insCode}")
    suspend fun getClosingPriceInfo(
        @Path("insCode") insCode: String
    ): Response<JsonObject>

    @GET("ClosingPrice/GetClosingPriceDailyList/{insCode}/{count}")
    suspend fun getDailyPrices(
        @Path("insCode") insCode: String,
        @Path("count") count: Int
    ): Response<JsonObject>
}

object TsetmcMarketApi {
    private const val BASE_URL = "https://cdn.tsetmc.com/api/"

    private val service: TsetmcMarketService by lazy {
        val headers = Interceptor { chain ->
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
            .addInterceptor(headers)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(45, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .build()

        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TsetmcMarketService::class.java)
    }

    suspend fun instrumentInfo(insCode: String): JsonObject =
        service.getInstrumentInfo(insCode).requirePayload("instrumentInfo")

    suspend fun closingPriceInfo(insCode: String): JsonObject =
        service.getClosingPriceInfo(insCode).requirePayload("closingPriceInfo")

    suspend fun dailyPrices(insCode: String, count: Int): JsonObject {
        require(count in 1..365) { "تعداد روزهای تاریخچه نامعتبر است." }
        return service.getDailyPrices(insCode, count)
            .requirePayload("closingPriceDaily")
    }

    private fun Response<JsonObject>.requirePayload(key: String): JsonObject {
        if (!isSuccessful) {
            throw TsetmcHttpException(code())
        }
        val body = body()
            ?: throw TsetmcInvalidResponseException("پاسخ TSETMC خالی است.")
        val payload = body.get(key)
        if (payload == null || payload.isJsonNull) {
            throw TsetmcInvalidResponseException("داده $key در پاسخ TSETMC موجود نیست.")
        }
        return if (payload.isJsonObject) {
            payload.asJsonObject
        } else {
            JsonObject().apply { add(key, payload) }
        }
    }
}
