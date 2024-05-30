package com.example.labelMark.utils;

import com.example.labelMark.service.TaskService;
import com.example.labelMark.service.TypeService;

import javax.annotation.Resource;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;


public class CovertCoordinateToPixel {

    private static TypeService typeService;

    public static void setTypeService(TypeService typeService) {
        CovertCoordinateToPixel.typeService = typeService;
    }

    // 将一组地理坐标转换为像素坐标，并生成相应的边界框和分割数组。
    public static List<Map<String, Object>> covertCoordinateToPixel(
            List<Map<String, Object>> arr,
            Map<String, Double> tifParams,
            Map<String, Double> dimensions) {

        if (typeService == null) {
            throw new IllegalStateException("TypeService has not been initialized.");
        }

        double tifMinx = tifParams.get("minx");
        double tifMaxy = tifParams.get("maxy");
        double serverHeight = tifParams.get("serverHeight");
        double serverWidth = tifParams.get("serverWidth");
        double width = dimensions.get("width");
        double height = dimensions.get("height");

        List<Map<String, Object>> bboxArr = new ArrayList<>();

        for (Map<String, Object> item : arr) {
            String geom = (String) item.get("geom");
            Integer taskId = (Integer) item.get("taskId");
            Integer userId = (Integer) item.get("userId");
            Integer typeId = (Integer) item.get("typeId");
            String typeColor = typeService.getColorById((Integer) item.get("typeId"));
            //初始化 resultArr（用于存储转换后的像素坐标）
            // xArray 和 yArray（用于存储原始地理坐标的 X 和 Y 值）
            String[] itemArr = geom.split(",");
            List<Double> resultArr = new ArrayList<>();
            List<Double> xArray = new ArrayList<>();
            List<Double> yArray = new ArrayList<>();

            // 遍历 itemArr 数组，偶数索引代表 X 坐标，奇数索引代表 Y 坐标。
            // 将地理坐标转换为像素坐标，并添加到 resultArr 中
            // 将原始 X 坐标添加到 xArray，将原始 Y 坐标添加到 yArray
            for (int i = 0; i < itemArr.length; i++) {
                if (i % 2 == 0) {
                    double currentX = Double.parseDouble(itemArr[i]);
                    resultArr.add(((currentX - tifMinx) / serverWidth) * width);
                    xArray.add(currentX);
                } else {
                    double currentY = Double.parseDouble(itemArr[i]);
                    resultArr.add(((tifMaxy - currentY) / serverHeight) * height);
                    yArray.add(currentY);
                }
            }
            // 找到 xArray 和 yArray 中的最小值和最大值
            double minX = xArray.stream().min(Double::compare).orElse(0.0);
            double minY = yArray.stream().min(Double::compare).orElse(0.0);
            double maxX = xArray.stream().max(Double::compare).orElse(0.0);
            double maxY = yArray.stream().max(Double::compare).orElse(0.0);
            // 根据最小值和最大值计算像素坐标边界框
            double pixMinx = ((minX - tifMinx) / serverWidth) * width;
            double pixMiny = ((tifMaxy - minY) / serverHeight) * height;
            double pixMaxx = ((maxX - tifMinx) / serverWidth) * width;
            double pixMaxy = ((tifMaxy - maxY) / serverHeight) * height;

            Map<String, Object> bboxItem = new HashMap<>();
            bboxItem.put("geom", geom);
            bboxItem.put("task_id", taskId);
            bboxItem.put("user_id", userId);
            bboxItem.put("type_id", typeId);
            bboxItem.put("type_color", typeColor);
            bboxItem.put("segmentation", resultArr);
            bboxItem.put("bbox", new double[]{pixMinx, pixMaxy, pixMaxx - pixMinx, pixMiny - pixMaxy});
            bboxItem.put("geoBbox", String.format("%f,%f,%f,%f", minX, minY, maxX, maxY));

            bboxArr.add(bboxItem);
        }

        return bboxArr;
    }
}
