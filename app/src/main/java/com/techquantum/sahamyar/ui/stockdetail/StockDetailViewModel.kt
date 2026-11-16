package com.techquantum.sahamyar.ui.stockdetail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.techquantum.sahamyar.data.repository.StockOverviewData
import com.techquantum.sahamyar.data.repository.StockRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class StockDetailState(
    val isLoading: Boolean = false,
    val data: StockOverviewData? = null,
    val error: String? = null
)

class StockDetailViewModel : ViewModel() {

    private val repository = StockRepository()
    private val _state = MutableStateFlow(StockDetailState())
    val state: StateFlow<StockDetailState> = _state.asStateFlow()

    private var loadedInsCode: String? = null
    private var activeRequestId = 0L
    private var activeJob: Job? = null

    fun loadStock(insCode: String, forceRefresh: Boolean = false) {
        if (insCode.isBlank()) {
            activeRequestId++
            activeJob?.cancel()
            activeJob = null
            loadedInsCode = null
            _state.value = StockDetailState(error = "کد نماد معتبر نیست.")
            return
        }

        if (!forceRefresh && loadedInsCode == insCode && _state.value.data != null) {
            return
        }

        activeJob?.cancel()
        val requestId = ++activeRequestId
        loadedInsCode = insCode
        _state.value = StockDetailState(isLoading = true)

        activeJob = viewModelScope.launch {
            val result = repository.getStockOverview(insCode)

            if (requestId != activeRequestId) return@launch

            result.fold(
                onSuccess = { data ->
                    _state.value = StockDetailState(data = data)
                },
                onFailure = { error ->
                    _state.value = StockDetailState(
                        error = error.message ?: "خطا در دریافت اطلاعات نماد"
                    )
                }
            )
        }
    }
}
