package com.tracker.api.controller;

import com.tracker.api.dto.StatsResponse;
import com.tracker.api.exception.InvalidFilterParamException;
import com.tracker.api.service.StatsService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import java.util.List;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(StatsController.class)
class StatsControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean StatsService statsService;

    @Test
    void getStats_returnsOk() throws Exception {
        var typeItem = new StatsResponse.TypeDistributionItem("매크로_판매", 5L);
        var siteItem = new StatsResponse.SiteDistributionItem("tailstar.net", 3L);
        var langItem = new StatsResponse.LangDistributionItem("zh-CN", 4L);
        var response = new StatsResponse(10L, 2L,
                List.of(typeItem), List.of(siteItem), List.of(langItem), List.of(), List.of());
        when(statsService.getStats(null, null)).thenReturn(response);

        mockMvc.perform(get("/api/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.todayCount").value(10))
                .andExpect(jsonPath("$.deltaFromYesterday").value(2))
                .andExpect(jsonPath("$.typeDistribution[0].type").value("매크로_판매"))
                .andExpect(jsonPath("$.typeDistribution[0].count").value(5))
                .andExpect(jsonPath("$.siteDistribution[0].site").value("tailstar.net"))
                .andExpect(jsonPath("$.langDistribution[0].lang").value("zh-CN"))
                .andExpect(jsonPath("$.trend").isArray())
                .andExpect(header().exists("X-Correlation-ID"));
    }

    @Test
    void getStats_withPeriodWeekly_returnsTrend() throws Exception {
        var trendItem = new StatsResponse.TrendItem("2026-04-30", 5L);
        var response = new StatsResponse(10L, 2L, List.of(), List.of(), List.of(), List.of(trendItem), List.of());
        when(statsService.getStats("weekly", null)).thenReturn(response);

        mockMvc.perform(get("/api/stats").param("period", "weekly"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.trend[0].date").value("2026-04-30"))
                .andExpect(jsonPath("$.trend[0].count").value(5));

        verify(statsService).getStats("weekly", null);
    }

    @Test
    void getStats_withDays_returnsTrend() throws Exception {
        var response = new StatsResponse(10L, 2L, List.of(), List.of(), List.of(), List.of(), List.of());
        when(statsService.getStats(null, 14)).thenReturn(response);

        mockMvc.perform(get("/api/stats").param("days", "14"))
                .andExpect(status().isOk());

        verify(statsService).getStats(null, 14);
    }

    @Test
    void getStats_withInvalidPeriod_returnsBadRequest() throws Exception {
        when(statsService.getStats("daily", null))
                .thenThrow(new InvalidFilterParamException("days는 1~365 사이 숫자만 허용됩니다."));

        mockMvc.perform(get("/api/stats").param("period", "daily"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("INVALID_FILTER_PARAM"));
    }
}
