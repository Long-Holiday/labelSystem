package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelMark.domain.Server;
import com.example.labelMark.domain.sysFile;
import com.example.labelMark.mapper.sysFileMapper;
import com.example.labelMark.service.sysFileService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Service
public class sysFileServiceImpl extends ServiceImpl<sysFileMapper, sysFile> implements sysFileService {

    @Resource
    private sysFileMapper sysfileMapper;
    @Override
    public List<sysFile> getAllFiles(Integer current, Integer pageSize, Integer fileId) {
        int offset = pageSize * (current - 1);
        List<sysFile> sysFiles = sysfileMapper.getAllFiles(current,pageSize,fileId,offset );
        return sysFiles;
    }

    @Override
    public void updateFile(Integer fileId, String fileName) {
        sysfileMapper.updateFile(fileId, fileName);
    }

    @Override
    public void deleteFile(String fileName) {
        QueryWrapper<sysFile> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("file_name", fileName);
        sysfileMapper.delete(queryWrapper);

    }
}
