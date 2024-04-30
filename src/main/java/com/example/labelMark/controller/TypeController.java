package com.example.labelMark.controller;

import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.TypeService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;

@RestController
@RequestMapping("/type")
@Api(tags = "类型业务控制器")
public class TypeController {

    @Resource
    private TypeService typeService;

    @GetMapping("/getTypes")
    @ApiOperation("获取类型")
    public Result getType(Integer current,
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
            return ResultGenerator.getSuccessResult(types);
        } catch (Exception e) {
            System.out.println("获取类型失败: " + e.getMessage());
            return ResultGenerator.getFailResult("获取类型失败");
        }
    }

    @PostMapping ("/createType")
    public Result createType(Integer typeId, String typeName){

        // 获取数据库TypeId种类
        List<Integer> IDs = typeService.getId();

        if(IDs.contains(typeId)){
            return ResultGenerator.getFailResult("该id已存在，请重新输入");
        }else {
            // 创建type
            typeService.createType(typeId,typeName);
            return ResultGenerator.getSuccessResult();
        }
    }

    @PutMapping ("/updateType")
    public Result updateType(Type type){
        typeService.updateType(type);
        return ResultGenerator.getSuccessResult();
    }

    @DeleteMapping("/deleteTypeById")
    public Result deleteTypeById(Integer typeId){
        typeService.deleteTypeById(typeId);
        return ResultGenerator.getSuccessResult();
    }

    @GetMapping("/getTypeById")
    public Result getTypeById(Integer typeId){
        Type type = typeService.getTypeById(typeId);
        return ResultGenerator.getSuccessResult(type);
    }

    @GetMapping("/getTypeNameById")
    public Result getTypeNameById(Integer typeId){
        String name = typeService.getTypeNameById(typeId);
        return ResultGenerator.getSuccessResult(name);
    }

}

