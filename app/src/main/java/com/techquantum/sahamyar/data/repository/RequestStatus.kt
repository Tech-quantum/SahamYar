package com.techquantum.sahamyar.data.repository

enum class RequestStatus {
    SUCCESS,
    NETWORK_ERROR,
    HTTP_ERROR,
    INVALID_DATA,
    INSUFFICIENT_DATA,
    NOT_SUPPORTED
}

data class RequestResult<out T>(
    val data: T?,
    val status: RequestStatus,
    val message: String? = null
)
