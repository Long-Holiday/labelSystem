package com.example.labelMark.utils;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;


public class CoordinateConverter {
//转化坐标信息（geojson）
    public static List<Map<String, Object>> convertCoordinate(List<Map<String, Object>> geojsonArr) {
        List<Map<String, Object>> geometryArr = new ArrayList<>();

        for (Map<String, Object> item : geojsonArr) {
            List<Object> extentArr = (List<Object>) item.get("extentArr");
            String typeid = (String) item.get("typeId");

            if (extentArr != null) {
                for (Object feature : extentArr) {
                    StringBuilder itemArr = new StringBuilder();
                    flattenCoordinates(feature, itemArr);

                    Map<String, Object> geometryMap = new HashMap<>();
                    geometryMap.put("geom", itemArr.toString());
                    geometryMap.put("typeId", typeid);

                    geometryArr.add(geometryMap);
                }
            }
        }

        return geometryArr;
    }

    private static void flattenCoordinates(Object feature, StringBuilder itemArr) {
        if (feature instanceof List) {
            for (Object element : (List<?>) feature) {
                flattenCoordinates(element, itemArr);
            }
        } else {
            if (itemArr.length() > 0) {
                itemArr.append(", ");
            }
            itemArr.append(feature.toString());
        }
    }
//处理标注信息
    public static List<Map<String, Object>> processMarkInfo(List<Map<String, Object>> geometryArr, List<String> typeArr) {
        List<Map<String, Object>> markInfoArr = new ArrayList<>();

        for (String typeid : typeArr) {
            List<Map<String, Object>> filteredItems = geometryArr.stream()
                    //TODO 改一下命名规范typeid--->typeId
                    .filter(item -> typeid.equals(item.get("typeId")))
                    .collect(Collectors.toList());

            markInfoArr.addAll(filteredItems);
        }

        return markInfoArr;

        // 处理 markInfoArr，例如保存数据到数据库
        // ...
    }
}

