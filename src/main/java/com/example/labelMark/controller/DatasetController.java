package com.example.labelMark.controller;

import com.example.labelMark.domain.Dataset;
import com.example.labelMark.service.DatasetService;
import com.example.labelMark.vo.constant.Result;
import com.example.labelMark.utils.ResultGenerator;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * <p>
 * 数据集控制器
 * </p>
 *
 * @author hjw
 * @since 2024-05-08
 */
@RestController
@RequestMapping("/dataset")
public class DatasetController {

    @Resource
    private DatasetService datasetService;

    /**
     * 发布共享数据集
     * 
     * @param params 请求参数
     * @return 结果
     */
    @PostMapping("/publishSharedDataset")
    public Result publishSharedDataset(@RequestBody Map<String, Object> params) {
        try {
            @SuppressWarnings("unchecked")
            List<String> sampleIds = (List<String>) params.get("sampleIds");
            String name = (String) params.get("name");
            String setDess = (String) params.get("setDess");
            String cont = (String) params.get("cont");
            String email = (String) params.get("email");
            Integer goal = 0; // 默认积分为0
            if (params.containsKey("goal") && params.get("goal") != null) {
                try {
                    Object goalObj = params.get("goal");
                    if (goalObj instanceof Integer) {
                        goal = (Integer) goalObj;
                    } else if (goalObj instanceof Double) {
                        goal = ((Double) goalObj).intValue();
                    } else {
                        String goalStr = goalObj.toString().trim();
                        if (!goalStr.isEmpty()) {
                            goal = Integer.parseInt(goalStr);
                        }
                    }
                    if (goal < 0) goal = 0; // 确保积分为非负
                } catch (NumberFormatException e) {
                    goal = 0; // 解析失败默认为0
                }
            }
            
            if (sampleIds == null || sampleIds.isEmpty()) {
                return ResultGenerator.getFailResult("样本ID不能为空");
            }
            
            if (name == null || name.trim().isEmpty()) {
                return ResultGenerator.getFailResult("数据集名称不能为空");
            }
            
            Integer datasetId = datasetService.publishSharedDataset(sampleIds, name, setDess, cont, email, goal);
            
            if (datasetId == null) {
                return ResultGenerator.getFailResult("发布共享数据集失败");
            }
            
            return ResultGenerator.getSuccessResult(datasetId);
        } catch (Exception e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult("发布共享数据集失败：" + e.getMessage());
        }
    }
    
    /**
     * 根据用户ID查询数据集
     * 
     * @param userId 用户ID
     * @return 结果
     */
    @GetMapping("/findDatasetByUserId")
    public Result findDatasetByUserId(@RequestParam Integer userId) {
        try {
            List<Dataset> datasets = datasetService.findDatasetByUserId(userId);
            return ResultGenerator.getSuccessResult(datasets);
        } catch (Exception e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult("查询数据集失败：" + e.getMessage());
        }
    }
    
    /**
     * 查询所有数据集
     * 
     * @return 结果
     */
    @GetMapping("/findAllDatasets")
    public Result findAllDatasets() {
        try {
            List<Dataset> datasets = datasetService.findAllDatasets();
            return ResultGenerator.getSuccessResult(datasets);
        } catch (Exception e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult("查询所有数据集失败：" + e.getMessage());
        }
    }
} 