package com.example.labelMark.service.impl;

import com.example.labelMark.domain.Mark;
import com.example.labelMark.mapper.MarkMapper;
import com.example.labelMark.service.MarkService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@Service
public class MarkServiceImpl extends ServiceImpl<MarkMapper, Mark> implements MarkService {

    private MarkMapper markMapper;

    @Override
    public boolean isMark(int taskId) {
        int count = markMapper.isMark(taskId);
        if(count != 0){
            return true;
        }else {
            return false;
        }
    }

    @Override
    public void createMark(int taskId, int typeId, String geom) {
        markMapper.createMark(taskId, typeId, geom);
    }

    @Override
    public void deleteMarkByName(String markName) {
        markMapper.deleteMarkByName(markName);
    }


    @Override
    public void deleteMark(int taskId, int typeId) {
        markMapper.deleteMark(taskId, typeId);
    }

//    @Override
//    public void createMark(String markName) {
//        markMapper.createMark(markName);
//    }
}
