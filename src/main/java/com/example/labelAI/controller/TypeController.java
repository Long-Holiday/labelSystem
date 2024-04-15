package com.example.labelAI.controller;

import com.example.labelAI.domain.Type;
import com.example.labelAI.service.TypeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.parameters.P;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/type")
public class TypeController {

    @Autowired
    private TypeService typeService;

    @GetMapping("/getTypes")
    public Result<List<Type>> getType(Integer current,
                                      Integer pageSize,
                                      @RequestParam(required = false)Integer typeId,
                                      @RequestParam(required = false)String typeName) {
        try {
            List<Type> types = typeService.getTypes(current, pageSize, typeId, typeName);
            // 是否需要获取types的数量？
//            int total = 0;
//            Integer typeId = type.getTypeId();
//            String typeName = type.getTypeName();
//            if (typeId != null || typeName != null) {
//                total = types.size();
//            }
            return Result.success(types);
        } catch (Exception e) {
            System.out.println("获取类型失败: " + e.getMessage());
            return Result.error("获取类型失败");
        }
    }

    @GetMapping ("/createType")
    public Result createType(Integer typeId, String typeName){

        // 获取数据库TypeId种类
        List<Integer> IDs = typeService.getId();

        if(IDs.contains(typeId)){
            return Result.error("该id已存在，请重新输入");
        }else {
            // 创建type
            typeService.createType(typeId,typeName);
            return Result.success();
        }
    }

    @PutMapping ("/updateType")
    public Result updateType(Type type){
        typeService.updateType(type);
        return Result.success();
    }

    @DeleteMapping("/deleteTypeById")
    public Result deleteTypeById(Integer typeId){
        typeService.deleteTypeById(typeId);
        return Result.success();
    }

    @GetMapping("/getTypeById")
    public Result<Type> getTypeById(Integer typeId){
        Type type = typeService.getTypeById(typeId);
        return Result.success(type);
    }

    @GetMapping("/getTypeNameById")
    public Result<String> getTypeNameById(Integer typeId){
        String name = typeService.getTypeNameById(typeId);
        return Result.success(name);
    }

}

